#!/usr/bin/env python3
"""
Actualiza index.html del Dashboard Touron con los datos de un correo
"Control regular de tareas y líneas por zonas, y expediciones SEUR/DHL - dd/mm/aaaa".

Uso:
    python3 bot/actualizar_dashboard.py <correo.txt> [--html index.html] [--dry-run]

<correo.txt> es el cuerpo en texto plano del correo (vale el reenviado).
Códigos de salida: 0 = actualizado, 3 = ese día ya estaba cargado, 1/2 = error.

Además, cada día se guarda en el archivo maestro datos/historico_libra.csv (todo el
histórico desde 2019, con zonas y expediciones desde octubre de 2026).

El histórico diario completo (desde el 29/09/2025) vive dentro del propio HTML en
<script type="application/json" id="estado-bot">. Este script solo añade el día nuevo
(y las zonas/expediciones del último día); la página calcula al cargarse todos los KPIs,
la temporada (octubre-septiembre), comparativas con el año anterior, medias y gráficos.
"""
import argparse, datetime as dt, json, math, re, sys

ZONAS = (1, 2, 3, 4, 5, 7)
DIA_C = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
DIA_L = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
MES_C = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
MES_L = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']


def miles(n):
    return f"{int(n):,}".replace(',', '.')


def dec(x, n=2):
    return f"{x:.{n}f}".replace('.', ',')


def num(s):
    return int(s.replace('.', '').replace(',', ''))


# ───────────────────────────── parseo del correo ─────────────────────────────
def parse_correo(txt):
    txt = txt.replace('\r', '').replace('\xa0', ' ')
    m = re.search(r'EXPEDICIONES\s*-\s*(\d{2})/(\d{2})/(\d{4})', txt)
    if not m:
        raise ValueError('No encuentro la línea "EXPEDICIONES - dd/mm/aaaa"')
    fecha = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    exp = {}
    for ag in ('SEUR', 'DHL'):
        m = re.search(rf'^\s*{ag}\s+([\d.]+)\s+([\d.]+)\s*$', txt, re.M)
        if not m:
            raise ValueError(f'No encuentro la fila de expediciones {ag}')
        exp[ag] = (num(m.group(1)), num(m.group(2)))
    m = re.search(r'TOTAL:\s*([\d.]+)\s+([\d.]+)', txt)
    if not m:
        raise ValueError('No encuentro la fila TOTAL: tareas líneas')
    tot_t, tot_l = num(m.group(1)), num(m.group(2))
    zonas = {}
    for m in re.finditer(r'^\s*(\d+)\s+ZONA DE TRABAJO\s+\d+\s+([\d.]+)\s+([\d.]+)\s*$', txt, re.M):
        zonas[int(m.group(1))] = (num(m.group(2)), num(m.group(3)))  # (tareas, líneas)
    if not zonas:
        raise ValueError('No encuentro filas de zonas')
    # La zona 5 tiene dos partes: "5 EMBARCACIONES" y "5 ZONA DE TRABAJO 5" (productos de gran
    # tamaño). Sus líneas se suman en la zona 5, como hace el TOTAL de LIBRA; las tareas de la
    # zona 5 se cuentan una sola vez, porque así cuadra el TOTAL de tareas de LIBRA.
    emb = (0, 0)
    m = re.search(r'^\s*5\s+EMBARCACIONES\s+([\d.]+)\s+([\d.]+)\s*$', txt, re.M)
    if m:
        emb = (num(m.group(1)), num(m.group(2)))
        t5, l5 = zonas.get(5, (0, 0))
        zonas[5] = (max(t5, emb[0]), l5 + emb[1])
    if sum(z[1] for z in zonas.values()) != tot_l or sum(z[0] for z in zonas.values()) != tot_t:
        raise ValueError(f'La suma de zonas no cuadra con el TOTAL ({tot_t} tareas / {tot_l} líneas): {zonas}')
    extra = set(zonas) - set(ZONAS)
    if extra:
        raise ValueError(f'Aparecen zonas nuevas {sorted(extra)}: el dashboard solo tiene {ZONAS}')
    for z in ZONAS:
        zonas.setdefault(z, (0, 0))
    return dict(fecha=fecha, tareas=tot_t, lineas=tot_l, cd=zonas[7][1], zonas=zonas, emb=emb, exp=exp)


# ───────────────────────────── actualización ───────────────────────────────
PAT = re.compile(r'(<script type="application/json" id="estado-bot">)(.*?)(</script>)', re.S)


def actualizar(html, d):
    """Añade el día al histórico JSON del HTML. La página calcula todo lo demás al cargarse."""
    m = PAT.search(html)
    if not m:
        raise RuntimeError('No encuentro el bloque <script id="estado-bot"> en el HTML')
    estado = json.loads(m.group(2))
    hist = estado['historico']  # [["aaaa-mm-dd", lineas, tareas, cd], ...]
    F = d['fecha']
    if any(x[0] == F.isoformat() for x in hist):
        return None
    if hist and F.isoformat() < hist[-1][0]:
        raise RuntimeError(f'La fecha {F} es anterior al último día cargado ({hist[-1][0]})')
    hist.append([F.isoformat(), d['lineas'], d['tareas'], d['cd']])
    estado['ultimo'] = {
        'fecha': F.isoformat(),
        'zonas': {str(k): list(v) for k, v in sorted(d['zonas'].items())},
        'embarcaciones': list(d['emb']),
        'expediciones': {k: list(v) for k, v in d['exp'].items()},
    }
    js = json.dumps(estado, ensure_ascii=False, separators=(',', ':'))
    new = html[:m.start()] + m.group(1) + js + m.group(3) + html[m.end():]
    se, sp = d['exp']['SEUR']; de, dp = d['exp']['DHL']
    resumen = dict(fecha=F.strftime('%d/%m/%Y'), lineas=d['lineas'], tareas=d['tareas'], cd=d['cd'],
                   bultos=se + sp + de + dp, dias_en_historico=len(hist))
    return new, resumen


# ───────────────────────────── archivo maestro CSV ──────────────────────────
COLS = ['TEMPORADA', 'SEMANA', 'DIA', 'FECHA', 'TAREAS', 'LINEAS', 'LINEAS_ARMARIOS', 'LINEAS_CD',
        'Z1_TAREAS', 'Z1_LINEAS', 'Z2_TAREAS', 'Z2_LINEAS', 'Z3_TAREAS', 'Z3_LINEAS', 'Z4_TAREAS', 'Z4_LINEAS',
        'Z5_TAREAS', 'Z5_LINEAS', 'Z5_EMB_TAREAS', 'Z5_EMB_LINEAS', 'Z7_TAREAS', 'Z7_LINEAS', 'SEUR_ESP', 'SEUR_POR', 'DHL_ESP', 'DHL_POR', 'FUENTE', 'NOTA']
DIA_LIBRA = ['1L', '2M', '3X', '4J', '5V', '6S', '7D']


def inicio_temporada(y):
    """Lunes de la semana del 1 de octubre (o el lunes siguiente si el 1/10 cae en fin de semana)."""
    o = dt.date(y, 10, 1)
    wd = o.weekday()
    return o + dt.timedelta(days=(7 - wd) if wd >= 5 else -wd)


def archivar(csv_path, d):
    """Añade (o completa) el día en el CSV maestro. Devuelve 'añadido', 'completado' o None si ya estaba."""
    import csv, os
    F = d['fecha']
    rows = []
    if os.path.exists(csv_path):
        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
    y = F.year if F >= inicio_temporada(F.year) else F.year - 1
    z, e = d['zonas'], d['exp']
    nueva = dict.fromkeys(COLS, '')
    nueva.update(TEMPORADA=(y + 1) % 100, SEMANA=(F - inicio_temporada(y)).days // 7 + 1,
                 DIA=DIA_LIBRA[F.weekday()], FECHA=F.strftime('%d/%m/%Y'),
                 TAREAS=d['tareas'], LINEAS=d['lineas'], LINEAS_CD=d['cd'],
                 SEUR_ESP=e['SEUR'][0], SEUR_POR=e['SEUR'][1], DHL_ESP=e['DHL'][0], DHL_POR=e['DHL'][1],
                 FUENTE='Correo LIBRA')
    for k in ZONAS:
        nueva[f'Z{k}_TAREAS'], nueva[f'Z{k}_LINEAS'] = z[k]
    nueva['Z5_EMB_TAREAS'], nueva['Z5_EMB_LINEAS'] = d['emb']
    accion = 'añadido'
    for r in rows:
        if r['FECHA'] == nueva['FECHA']:
            if r.get('Z1_LINEAS'):
                return None
            for c in COLS:                      # completar la fila existente (zonas/expediciones)
                if not r.get(c) and nueva[c] != '':
                    r[c] = nueva[c]
            r['FUENTE'] = (r.get('FUENTE') or '') + ' + correo LIBRA'
            accion = 'completado'
            break
    else:
        rows.append(nueva)
    rows.sort(key=lambda r: dt.datetime.strptime(r['FECHA'], '%d/%m/%Y'))
    os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, COLS, delimiter=';', extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return accion


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('correo')
    ap.add_argument('--html', default='index.html')
    ap.add_argument('--csv', default='datos/historico_libra.csv', help='archivo maestro con todo el histórico')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    d = parse_correo(open(a.correo, encoding='utf-8').read())
    html = open(a.html, encoding='utf-8').read()
    r = actualizar(html, d)
    arch = None if a.dry_run else archivar(a.csv, d)
    if r is None:
        if arch:
            print(f'SOLO_ARCHIVO {d["fecha"].strftime("%d/%m/%Y")}: ya estaba en el dashboard; {arch} en {a.csv}')
            return
        print(f'YA_CARGADO {d["fecha"].strftime("%d/%m/%Y")}: no se ha modificado nada')
        sys.exit(3)
    new, resumen = r
    if not a.dry_run:
        open(a.html, 'w', encoding='utf-8').write(new)
    resumen['archivo'] = arch or 'ya estaba'
    print('OK ' + json.dumps(resumen, ensure_ascii=False))


if __name__ == '__main__':
    main()
