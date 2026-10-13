#!/usr/bin/env python3
"""
Actualiza index.html del Dashboard Touron con los datos de un correo
"Control regular de tareas y líneas por zonas, y expediciones SEUR/DHL - dd/mm/aaaa".

Uso:
    python3 bot/actualizar_dashboard.py <correo.txt> [--html index.html] [--dry-run]

<correo.txt> es el cuerpo en texto plano del correo (vale el reenviado).
Códigos de salida: 0 = actualizado, 3 = ese día ya estaba cargado, 1/2 = error.

El histórico diario completo (desde el 29/09/2025) vive dentro del propio HTML en
<script type="application/json" id="estado-bot">. Este script solo añade el día nuevo
(y las zonas/expediciones del último día); la página calcula al cargarse todos los KPIs,
la temporada (octubre-septiembre), comparativas con el año anterior, medias y gráficos.
"""
import argparse, datetime as dt, json, math, re, sys

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
    if sum(z[1] for z in zonas.values()) != tot_l or sum(z[0] for z in zonas.values()) != tot_t:
        raise ValueError(f'La suma de zonas no cuadra con el TOTAL ({tot_t} tareas / {tot_l} líneas): {zonas}')
    extra = set(zonas) - {1, 2, 3, 4, 7}
    if extra:
        raise ValueError(f'Aparecen zonas nuevas {sorted(extra)}: el dashboard solo tiene 1,2,3,4 y 7')
    for z in (1, 2, 3, 4, 7):
        zonas.setdefault(z, (0, 0))
    return dict(fecha=fecha, tareas=tot_t, lineas=tot_l, cd=zonas[7][1], zonas=zonas, exp=exp)


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
        'expediciones': {k: list(v) for k, v in d['exp'].items()},
    }
    js = json.dumps(estado, ensure_ascii=False, separators=(',', ':'))
    new = html[:m.start()] + m.group(1) + js + m.group(3) + html[m.end():]
    se, sp = d['exp']['SEUR']; de, dp = d['exp']['DHL']
    resumen = dict(fecha=F.strftime('%d/%m/%Y'), lineas=d['lineas'], tareas=d['tareas'], cd=d['cd'],
                   bultos=se + sp + de + dp, dias_en_historico=len(hist))
    return new, resumen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('correo')
    ap.add_argument('--html', default='index.html')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    d = parse_correo(open(a.correo, encoding='utf-8').read())
    html = open(a.html, encoding='utf-8').read()
    r = actualizar(html, d)
    if r is None:
        print(f'YA_CARGADO {d["fecha"].strftime("%d/%m/%Y")}: no se ha modificado nada')
        sys.exit(3)
    new, resumen = r
    if not a.dry_run:
        open(a.html, 'w', encoding='utf-8').write(new)
    print('OK ' + json.dumps(resumen, ensure_ascii=False))


if __name__ == '__main__':
    main()
