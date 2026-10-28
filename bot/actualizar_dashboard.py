#!/usr/bin/env python3
"""
Actualiza index.html del Dashboard Touron con los datos de un correo
"Control regular de tareas y líneas por zonas, y expediciones SEUR/DHL - dd/mm/aaaa".

Uso:
    python3 bot/actualizar_dashboard.py <correo.txt> [--html index.html] [--dry-run]

<correo.txt> es el cuerpo en texto plano del correo (vale el reenviado).
Códigos de salida: 0 = actualizado (OK, CORREGIDO o SOLO_ARCHIVO), 3 = ese día ya estaba cargado, 1/2 = error.
Si el día ya estaba cargado desde el Excel con otros valores, manda el correo de LIBRA (CORREGIDO).

Además, cada día se guarda en el archivo maestro datos/historico_libra.csv (todo el
histórico desde 2019, con zonas y expediciones desde octubre de 2026).

El histórico diario completo (desde el 29/09/2025) vive dentro del propio HTML en
<script type="application/json" id="estado-bot">. Este script solo añade el día nuevo
(y las zonas/expediciones del último día); la página calcula al cargarse todos los KPIs,
la temporada (octubre-septiembre), comparativas con el año anterior, medias y gráficos.
"""
import argparse, datetime as dt, json, math, re, sys

ZONAS = (1, 2, 3, 4, 5, 6, 7)  # 6 = ZONA PORTUGAL
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
        if m:
            exp[ag] = (num(m.group(1)), num(m.group(2)))
        elif re.search(rf'^\s*{ag}\s*$', txt, re.M):
            exp[ag] = (0, 0)  # fila vacía (día sin actividad): se carga a 0
        else:
            raise ValueError(f'No encuentro la fila de expediciones {ag}')
    m = re.search(r'TOTAL:\s*([\d.]+)\s+([\d.]+)', txt)
    if not m:
        raise ValueError('No encuentro la fila TOTAL: tareas líneas')
    tot_t, tot_l = num(m.group(1)), num(m.group(2))
    zonas = {}
    for m in re.finditer(r'^\s*(\d+)\s+ZONA\s+(?:DE TRABAJO\s+\d+|PORTUGAL)\s+([\d.]+)\s+([\d.]+)\s*$', txt, re.M):
        zonas[int(m.group(1))] = (num(m.group(2)), num(m.group(3)))  # (tareas, líneas)
    if not zonas and (tot_t, tot_l) != (0, 0):
        raise ValueError('No encuentro filas de zonas')
    # TOTAL 0 0 sin filas de zonas = día sin actividad (domingo, festivo): todo se carga a 0.
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
    nuevo = [F.isoformat(), d['lineas'], d['tareas'], d['cd']]
    previo = next((x for x in hist if x[0] == F.isoformat()), None)
    if previo == nuevo:
        return None
    if previo is not None:
        # El correo de LIBRA tiene prioridad sobre el Excel: se corrige el día ya cargado.
        hist[hist.index(previo)] = nuevo
    elif hist and F.isoformat() < hist[-1][0]:
        if d['lineas'] or d['tareas']:
            raise RuntimeError(f'La fecha {F} es anterior al último día cargado ({hist[-1][0]})')
        # Día sin actividad atrasado: se intercala a 0 (la página ignora los días con 0 líneas).
        hist.append(nuevo)
        hist.sort(key=lambda x: x[0])
    else:
        hist.append(nuevo)
    # Un día a 0 no sustituye el detalle de zonas/expediciones del último día con actividad.
    if F.isoformat() == hist[-1][0] and d['lineas']:
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
    if previo is not None:
        resumen['corregido_antes'] = dict(lineas=previo[1], tareas=previo[2], cd=previo[3])
    return new, resumen


# ───────────────────────────── archivo maestro CSV ──────────────────────────
COLS = ['TEMPORADA', 'SEMANA', 'DIA', 'FECHA', 'TAREAS', 'LINEAS', 'LINEAS_ARMARIOS', 'LINEAS_CD',
        'Z1_TAREAS', 'Z1_LINEAS', 'Z2_TAREAS', 'Z2_LINEAS', 'Z3_TAREAS', 'Z3_LINEAS', 'Z4_TAREAS', 'Z4_LINEAS',
        'Z5_TAREAS', 'Z5_LINEAS', 'Z5_EMB_TAREAS', 'Z5_EMB_LINEAS', 'Z6_TAREAS', 'Z6_LINEAS', 'Z7_TAREAS', 'Z7_LINEAS', 'SEUR_ESP', 'SEUR_POR', 'DHL_ESP', 'DHL_POR', 'FUENTE', 'NOTA']
DIA_LIBRA = ['1L', '2M', '3X', '4J', '5V', '6S', '7D']


def inicio_temporada(y):
    """Lunes de la semana del 1 de octubre (o el lunes siguiente si el 1/10 cae en fin de semana)."""
    o = dt.date(y, 10, 1)
    wd = o.weekday()
    return o + dt.timedelta(days=(7 - wd) if wd >= 5 else -wd)


def archivar(csv_path, d):
    """Añade, completa o corrige el día en el CSV maestro (el correo de LIBRA tiene prioridad
    sobre el Excel). Devuelve 'añadido', 'completado', 'corregido' o None si ya estaba."""
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
            if 'correo' in (r.get('FUENTE') or '').lower() and r.get('Z1_LINEAS'):
                return None                     # ya venía del correo de LIBRA
            # El correo de LIBRA tiene prioridad sobre el Excel: se sobrescriben sus datos
            # (se conservan LINEAS_ARMARIOS y NOTA, que solo existen en el Excel).
            antes = (r.get('TAREAS'), r.get('LINEAS'), r.get('LINEAS_CD'))
            for c in COLS:
                if c not in ('LINEAS_ARMARIOS', 'NOTA', 'FUENTE') and nueva[c] != '':
                    r[c] = nueva[c]
            r['FUENTE'] = (r.get('FUENTE') or '') + ' + correo LIBRA'
            accion = 'completado'
            if antes != (str(d['tareas']), str(d['lineas']), str(d['cd'])):
                nota = f'Corregido con correo LIBRA (Excel: {antes[0]} tareas / {antes[1]} líneas / {antes[2]} C.D.)'
                r['NOTA'] = f"{r['NOTA']} | {nota}" if r.get('NOTA') else nota
                accion = 'corregido'
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
    print(('CORREGIDO ' if 'corregido_antes' in resumen else 'OK ') + json.dumps(resumen, ensure_ascii=False))


if __name__ == '__main__':
    main()
