#!/usr/bin/env python3
"""
Actualiza index.html del Dashboard Touron con los datos de un correo
"Control regular de tareas y líneas por zonas, y expediciones SEUR/DHL - dd/mm/aaaa".

Uso:
    python3 bot/actualizar_dashboard.py <correo.txt> [--html index.html] [--dry-run]

<correo.txt> es el cuerpo en texto plano del correo (vale el reenviado).
Códigos de salida: 0 = actualizado, 3 = ese día ya estaba cargado, 1/2 = error.

El histórico diario completo (desde el 29/09/2025) vive dentro del propio HTML en
<script type="application/json" id="estado-bot">, y a partir de él se recalculan
medias por día de la semana, días activos, C.D., meses, etc.
"""
import argparse, datetime as dt, json, math, re, sys

D0 = dt.date(2025, 9, 29)  # lunes de la Semana 1 del año 26
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


# ───────────────────────────── utilidades HTML ──────────────────────────────
class Html:
    def __init__(self, s):
        self.s = s

    def sub(self, pat, repl, flags=0):
        new, n = re.subn(pat, repl, self.s, count=1, flags=flags)
        if n != 1:
            raise RuntimeError(f'Patrón no encontrado en el HTML: {pat[:90]}')
        self.s = new

    def get(self, pat, flags=0):
        m = re.search(pat, self.s, flags)
        if not m:
            raise RuntimeError(f'Patrón no encontrado en el HTML: {pat[:90]}')
        return m


def js_list(txt):
    return json.loads(re.sub(r'([{,])(\w+):', r'\1"\2":', txt))


def js_dump(lst):
    out = []
    for o in lst:
        out.append('{' + ','.join(f'{k}:{json.dumps(v, ensure_ascii=False)}' for k, v in o.items()) + '}')
    return '[' + ','.join(out) + ']'


def arr(nums):
    return ','.join(str(x) for x in nums)


# ───────────────────────────── actualización ───────────────────────────────
def actualizar(html, d):
    h = Html(html)
    F = d['fecha']
    ddmm = F.strftime('%d/%m')
    ddmmyyyy = F.strftime('%d/%m/%Y')
    L, T, CD = d['lineas'], d['tareas'], d['cd']

    # Estado (histórico diario)
    m = h.get(r'<script type="application/json" id="estado-bot">(.*?)</script>', re.S)
    estado = json.loads(m.group(1))
    hist = estado['historico']  # [["aaaa-mm-dd", lineas, tareas, cd], ...]
    if any(x[0] == F.isoformat() for x in hist):
        return None
    if hist and F.isoformat() < hist[-1][0]:
        raise RuntimeError(f'La fecha {F} es anterior al último día cargado ({hist[-1][0]})')
    hist.append([F.isoformat(), L, T, CD])
    activos = [x for x in hist if x[1] > 0]
    n_act = len(activos)

    # semanas
    semanas = js_list(h.get(r'const semanas=(\[.*?\]);').group(1))
    k = (F - D0).days // 7 + 1
    if semanas[-1]['sem'] == k:
        semanas[-1]['lineas'] += L
        semanas[-1]['tareas'] += T
    elif k > semanas[-1]['sem']:
        semanas.append({'sem': k, 'lineas': L, 'tareas': T, 'fecha': ddmm})
    else:
        raise RuntimeError(f'Semana {k} anterior a la última del dashboard')
    h.sub(r'const semanas=\[.*?\];', lambda _: f'const semanas={js_dump(semanas)};')

    # diario
    diario = js_list(h.get(r'const diario=(\[.*?\]);').group(1))
    diario.append({'f': ddmm, 'd': DIA_C[F.weekday()], 'l': L, 't': T})
    h.sub(r'const diario=\[.*?\];', lambda _: f'const diario={js_dump(diario)};')

    # agregados
    tot_l = sum(s['lineas'] for s in semanas)
    tot_t = sum(s['tareas'] for s in semanas)
    ult = semanas[-1]['sem']
    media_dia = math.ceil(tot_l / n_act)
    media_t = int(tot_t / n_act)
    mejor = max(semanas, key=lambda s: s['lineas'])
    mj_d, mj_m = (int(x) for x in mejor['fecha'].split('/'))
    media_sem = math.ceil(tot_l / len(semanas))
    cd_tot = sum(x[3] for x in hist)
    cd_max = max(hist, key=lambda x: x[3])
    cd_max_f = dt.date.fromisoformat(cd_max[0]).strftime('%d/%m')

    def media_wd(i, col):
        xs = [x[col] for x in activos if dt.date.fromisoformat(x[0]).weekday() == i]
        return math.ceil(sum(xs) / len(xs)) if xs else 0
    wd_l = [media_wd(i, 1) for i in range(5)]
    wd_t = [media_wd(i, 2) for i in range(5)]
    wd_hoy = wd_l[F.weekday()] if F.weekday() < 5 else media_dia

    # ── PANTALLA 1 ──
    h.sub(r'Año 26 · Semanas 1–\d+', f'Año 26 · Semanas 1–{ult}')
    h.sub(r'(<div class="tstat-val">)[\d.]+(</div><div class="tstat-lbl">Líneas año)', rf'\g<1>{miles(tot_l)}\2')
    h.sub(r'(<div class="tstat-val" style="color:#15a468">)[\d.]+(</div><div class="tstat-lbl">Último día)', rf'\g<1>{L}\2')
    h.sub(r'(Total líneas año</div><div class="kpi-val b">)[\d.]+(</div></div><div><div class="kpi-sub">S1 \(29 sep\) → S)\d+',
          rf'\g<1>{miles(tot_l)}\g<2>{ult}')
    delta = (f'<div class="delta dd">↓ {DIA_L[F.weekday()]} bajo</div>' if L < wd_hoy
             else f'<div class="delta du">↑ {DIA_L[F.weekday()]} alto</div>')
    h.sub(r'<div class="kpi-lbl">Último día · [\d/]+</div><div class="kpi-val g">[\d.]+</div></div><div><div class="kpi-sub">[^<]*</div><div class="delta [^"]*">[^<]*</div>',
          f'<div class="kpi-lbl">Último día · {ddmm}</div><div class="kpi-val g">{miles(L)}</div></div>'
          f'<div><div class="kpi-sub">{T} tareas · C.D.: {CD}</div>{delta}')
    h.sub(r'(Media diaria</div><div class="kpi-val o">)[\d.]+', rf'\g<1>{miles(media_dia)}')
    h.sub(r'Mejor semana \(S\d+\)</div><div class="kpi-val p">[\d.]+</div></div><div><div class="kpi-sub">Semana [^<]*',
          f'Mejor semana (S{mejor["sem"]})</div><div class="kpi-val p">{miles(mejor["lineas"])}</div></div>'
          f'<div><div class="kpi-sub">Semana {mj_d} {MES_C[mj_m-1].lower()}')
    h.sub(r'(Total tareas año</div><div class="kpi-val c">)[\d.]+(</div></div><div><div class="kpi-sub">)Media \d+/día · ratio [\d,]+',
          rf'\g<1>{miles(tot_t)}\g<2>Media {media_t}/día · ratio {dec(tot_l/tot_t)}')
    h.sub(r'(>Ayer · )[\d/]+(</div>\s*<div[^>]*>)[\d.]+(</div>)', rf'\g<1>{ddmmyyyy}\g<2>{miles(L)}\3')
    h.sub(r'<span>\d+ tareas</span><span style="opacity:.5">·</span><span>C.D.: \d+</span>',
          f'<span>{T} tareas</span><span style="opacity:.5">·</span><span>C.D.: {CD}</span>')
    h.sub(r'Año completo \(semanas 1 a \d+\)', f'Año completo (semanas 1 a {ult})')
    h.sub(r'Récord · S\d+', f'Récord · S{mejor["sem"]}')
    h.sub(r'(Media semanal <strong style="color:var\(--cyan\)">)[\d.]+', rf'\g<1>{miles(media_sem)}')
    # bloque C.D.
    h.sub(r'(Líneas C.D. · Zona 7</div>\s*<div[^>]*>)[\d.]+(</div>\s*<div[^>]*>)ayer [\d/]+ · \d+% del total',
          rf'\g<1>{CD}\g<2>ayer {ddmm} · {round(CD/L*100) if L else 0}% del total')
    h.sub(r'(>Total año</div>\s*<div[^>]*>)[\d.]+(</div>\s*<div[^>]*>)\d+% del total',
          rf'\g<1>{miles(cd_tot)}\g<2>{round(cd_tot/tot_l*100)}% del total')
    h.sub(r'(>Media/día</div>\s*<div[^>]*>)[\d.]+', rf'\g<1>{math.ceil(cd_tot/n_act)}')
    h.sub(r'(>Máximo</div>\s*<div[^>]*>)[\d.]+(</div>\s*<div[^>]*>)[\d/]+', rf'\g<1>{cd_max[3]}\g<2>{cd_max_f}')

    # ── PANTALLA 2 ──
    d60 = diario[-60:]
    media_per = math.ceil(sum(x['l'] for x in d60) / len(d60))
    h.sub(r'const mediaAnualReal=\d+;[^\n]*',
          f'const mediaAnualReal={media_dia}; // media diaria del año ({miles(tot_l)} líneas / {n_act} días activos), redondeada al alza')
    h.sub(r'(Media período <strong style="color:#c06000">)[\d.]+', rf'\g<1>{media_per}')
    h.sub(r'(Media año <strong style="color:#6b52d0">)[\d.]+', rf'\g<1>{media_dia}')
    h.sub(r"(\{label:'Líneas',data:)\[[\d,]+\](,backgroundColor:'#2b7de9',borderRadius:6,barPercentage:0.5\})",
          rf'\g<1>[{arr(wd_l)}]\2')
    h.sub(r"(\{label:'Tareas',data:)\[[\d,]+\](,backgroundColor:'rgba\(10,180,195,.65\)')",
          rf'\g<1>[{arr(wd_t)}]\2')

    # ── PANTALLA 3 ──
    titulo = f'{DIA_L[F.weekday()].capitalize()} {F.day} {MES_L[F.month-1]} {F.year}'
    h.sub(r'Desglose por Zonas · [^<]+', f'Desglose por Zonas · {titulo}')
    h.sub(r'(<div class="tstat-val" style="color:#15a468">)[\d.]+(</div><div class="tstat-lbl">Líneas</div>)', rf'\g<1>{L}\2')
    h.sub(r'(<div class="tstat-val" style="color:#e07010">)[\d.]+(</div><div class="tstat-lbl">Tareas</div>)', rf'\g<1>{T}\2')
    h.sub(r'(<div class="tstat-val" style="color:#0ab4c3">)[\d.]+(</div><div class="tstat-lbl">C.D.</div>)', rf'\g<1>{CD}\2')
    h.sub(r'Líneas y tareas por zona · [\d/]+</div><div class="cbadge cb-blue">[\d.]+ líneas totales',
          f'Líneas y tareas por zona · {ddmmyyyy}</div><div class="cbadge cb-blue">{miles(L)} líneas totales')
    z = d['zonas']
    maxz = max(z[i][1] for i in (1, 2, 3, 4, 7)) or 1
    def fila(i):
        t_, l_ = z[i]
        ratio = dec(l_ / t_) if t_ else '–'
        pct = dec(l_ / L * 100, 1) + '%' if L else '–'
        w = round(l_ / maxz * 100)
        return ratio, pct, w
    for i in (1, 2, 3, 4):
        ratio, pct, w = fila(i)
        h.sub(rf'<tr><td>Zona {i}</td><td class="bv">\d+</td><td class="r">\d+</td><td class="r">[^<]*</td><td class="r">[^<]*</td><td><span class="zbar" style="width:\d+px',
              f'<tr><td>Zona {i}</td><td class="bv">{z[i][1]}</td><td class="r">{z[i][0]}</td><td class="r">{ratio}</td><td class="r">{pct}</td><td><span class="zbar" style="width:{w}px')
    ratio, pct, w = fila(7)
    h.sub(r'(Z7 · C.D.</td><td class="bv" style="color:var\(--cyan\)">)\d+(</td><td class="r">)\d+(</td><td class="r">)[^<]*(</td><td class="r" style="[^"]*">)[^<]*(</td><td><span class="zbar" style="width:)\d+',
          rf'\g<1>{z[7][1]}\g<2>{z[7][0]}\g<3>{ratio}\g<4>{pct}\g<5>{w}')
    h.sub(r'<tfoot><tr><td>Total día</td><td>[\d.]+</td><td>\d+</td><td>[\d,]+</td>',
          f'<tfoot><tr><td>Total día</td><td>{miles(L)}</td><td>{T}</td><td>{dec(L/T) if T else "–"}</td>')
    h.sub(r"(labels:\['Zona 1','Zona 2','Zona 3','Zona 4','Z7 C.D.'\],\s*datasets:\[\s*\{label:'Líneas',data:)\[[\d,]+\]",
          rf'\g<1>[{arr(z[i][1] for i in (1,2,3,4,7))}]')
    h.sub(r"(\{label:'Tareas',data:)\[[\d,]+\](,\s*backgroundColor:\['rgba\(43,125,233,.25\)')",
          rf'\g<1>[{arr(z[i][0] for i in (1,2,3,4,7))}]\2')

    # KPIs del mes
    def mes(y, mth):
        return [x for x in activos if x[0].startswith(f'{y:04d}-{mth:02d}-')]
    cur = mes(F.year, F.month)
    py, pm = (F.year, F.month - 1) if F.month > 1 else (F.year - 1, 12)
    prev = mes(py, pm)
    m_cur = math.ceil(sum(x[1] for x in cur) / len(cur))
    m_prev = math.ceil(sum(x[1] for x in prev) / len(prev)) if prev else 0
    var = round((m_cur - m_prev) / m_prev * 100) if m_prev else 0
    vtxt = (f'<div class="delta dd">↓ {var}%</div>' if var < 0 else f'<div class="delta du">↑ +{var}%</div>')
    h.sub(r'Media diaria \w+</div><div class="kpi-val g" style="font-size:2.6rem">[\d.]+</div></div><div><div class="kpi-sub">vs \w+ [\d.]+</div><div class="delta [^"]*">[^<]*</div>',
          f'Media diaria {MES_L[F.month-1]}</div><div class="kpi-val g" style="font-size:2.6rem">{miles(m_cur)}</div></div>'
          f'<div><div class="kpi-sub">vs {MES_L[pm-1]} {miles(m_prev)}</div>{vtxt}')
    h.sub(r'Total líneas \w+</div><div class="kpi-val c" style="font-size:2.6rem">[\d.]+</div></div><div><div class="kpi-sub">\d+ días? activos? \(S\d+\)',
          f'Total líneas {MES_L[F.month-1]}</div><div class="kpi-val c" style="font-size:2.6rem">{miles(sum(x[1] for x in cur))}</div></div>'
          f'<div><div class="kpi-sub">{len(cur)} {"día activo" if len(cur)==1 else "días activos"} (S{ult})')

    # Expediciones
    se, sp = d['exp']['SEUR']; de, dp = d['exp']['DHL']
    h.sub(r'Expediciones · [\d/]+</div>\s*<div class="cbadge cb-purple">[\d.]+ bultos',
          lambda _: f'Expediciones · {ddmmyyyy}</div>\n          <div class="cbadge cb-purple">{miles(se+sp+de+dp)} bultos')
    num_td = r'(<td style="padding:8px 6px;text-align:right;[^"]*">)[\d.]+(</td>)'
    for ag, (e, p) in (('SEUR', (se, sp)), ('DHL', (de, dp))):
        h.sub(rf'({ag}</td>\s*){num_td}(\s*){num_td}(\s*){num_td}',
              rf'\g<1>\g<2>{e}\g<3>\g<4>\g<5>{p}\g<6>\g<7>\g<8>{e+p}\g<9>')
    h.sub(r'(<td style="padding:8px 6px;text-align:right;font-weight:800">)[\d.]+(</td>\s*<td style="padding:8px 6px;text-align:right;font-weight:800">)[\d.]+(</td>\s*<td style="padding:8px 6px;text-align:right;font-weight:900;font-size:16px;color:var\(--purple\)">)[\d.]+',
          rf'\g<1>{se+de}\g<2>{sp+dp}\g<3>{miles(se+sp+de+dp)}')

    # Detalle del mes (últimos 5 días)
    u5 = diario[-5:]
    h.sub(r'Detalle \w+ \d{4}</div><div class="cbadge cb-green">', f'Detalle {MES_L[F.month-1]} {F.year}</div><div class="cbadge cb-green">')
    m = h.get(r"new Chart\(document.getElementById\('cJulio'\).*?\n\}\);", re.S)
    blk = m.group(0)
    blk = re.sub(r"labels:\[\[.*?\]\],", 'labels:[' + ','.join(f"['{x['f']}','{x['d']}']" for x in u5) + '],', blk, count=1)
    blk = re.sub(r"(\{label:'Líneas',data:)\[[\d,]+\]", rf"\g<1>[{arr(x['l'] for x in u5)}]", blk, count=1)
    blk = re.sub(r"(\{label:'Tareas',data:)\[[\d,]+\]", rf"\g<1>[{arr(x['t'] for x in u5)}]", blk, count=1)
    ymax = max(850, math.ceil(max(x['l'] for x in u5) / 50) * 50 + 50)
    blk = re.sub(r'min:0,max:\d+', f'min:0,max:{ymax}', blk, count=1)
    h.s = h.s.replace(m.group(0), blk)

    # Mensual
    m = h.get(r"new Chart\(document.getElementById\('cMensual'\).*?\n\}\);", re.S)
    blk = m.group(0)
    labels = re.findall(r"'([^']*)'", re.search(r'labels:\[(.*?)\]', blk).group(1))
    data = [int(x) for x in re.search(r'data:\[([\d,]+)\]', blk).group(1).split(',')]
    cols = re.findall(r"'(#[0-9a-f]+)'", re.search(r'pointBackgroundColor:\[(.*?)\]', blk).group(1))
    cur_lbl = MES_C[F.month-1] + '*'
    if labels[-1] == cur_lbl:
        data[-1] += L
    else:
        labels = [x.rstrip('*') for x in labels[1:]] + [cur_lbl]
        data = data[1:] + [L]
        cols = cols[1:] + ['#2b7de9']
        # ventana de 12 meses: empieza en el mes siguiente al actual del año anterior
        f_y = F.year if F.month == 12 else F.year - 1
        h.sub(r'Tendencia mensual · \w+ \d+ → \w+ \d+',
              f'Tendencia mensual · {MES_C[F.month % 12]} {str(f_y)[2:]} → {MES_C[F.month-1]} {str(F.year)[2:]}')
    blk = re.sub(r'labels:\[.*?\]', 'labels:[' + ','.join(f"'{x}'" for x in labels) + ']', blk, count=1)
    blk = re.sub(r'data:\[[\d,]+\]', f'data:[{arr(data)}]', blk, count=1)
    blk = re.sub(r'pointBackgroundColor:\[.*?\]', 'pointBackgroundColor:[' + ','.join(f"'{c}'" for c in cols) + ']', blk, count=1)
    h.s = h.s.replace(m.group(0), blk)

    # Mini-gráfico C.D.
    m = h.get(r"new Chart\(document.getElementById\('cCD'\).*?\n\}\);", re.S)
    blk = m.group(0)
    labels = re.findall(r"'([^']*)'", re.search(r'labels:\[(.*?)\]', blk).group(1))
    data = [int(x) for x in re.search(r'data:\[([\d,]+)\]', blk).group(1).split(',')]
    labels = labels[1:] + [ddmm]
    data = data[1:] + [CD]
    blk = re.sub(r'labels:\[.*?\]', 'labels:[' + ','.join(f"'{x}'" for x in labels) + ']', blk, count=1)
    blk = re.sub(r'data:\[[\d,]+\]', f'data:[{arr(data)}]', blk, count=1)
    h.s = h.s.replace(m.group(0), blk)

    # Guardar estado
    estado['historico'] = hist
    estado['ultima_actualizacion'] = F.isoformat()
    h.sub(r'(<script type="application/json" id="estado-bot">).*?(</script>)',
          lambda m_: m_.group(1) + json.dumps(estado, separators=(',', ':')) + m_.group(2), re.S)

    resumen = dict(fecha=ddmmyyyy, lineas=L, tareas=T, cd=CD, semana=ult, total_lineas_anio=tot_l,
                   media_diaria=media_dia, dias_activos=n_act, bultos=se+sp+de+dp,
                   media_mes=m_cur, total_mes=sum(x[1] for x in cur))
    return h.s, resumen


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
