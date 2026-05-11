import requests, csv, io, os, json
from datetime import datetime, timedelta
import pytz

SHEET_ID = '1MNmYN39x8FB8BGBQocZGAL8kDGQ4WZ5B7uAy5KazJ1c'
WEBHOOK  = os.environ.get('DISCORD_WEBHOOK',
           'https://discord.com/api/webhooks/1503448814189809734/XeNe5njFg4CK_z0YUgKncxMNZVl_6W2li-yB1wfQgsVFE1nJfKIyY1JrA4p0V4AhHaVe')
BR_TZ    = pytz.timezone('America/Sao_Paulo')

META_LEADS_DIA = 40
META_INV_DIA   = 60.0
CAMP_END       = datetime(2026, 5, 30, tzinfo=pytz.utc)

# Emojis como escape Unicode (evita problema de encoding no Windows)
BOOK  = '\U0001F4D8'
CAL   = '\U0001F4C5'
CLK   = '⏰'
CHART = '\U0001F4CA'
TICK  = '\U0001F39F'
CASH  = '\U0001F4B0'
PIN   = '\U0001F4CC'
PTR   = '\U0001F449'
HOUR  = '⏳'
LINK  = '\U0001F517'
DART  = '\U0001F3AF'
MAG   = '\U0001F50D'
OK    = '✅'
WARN  = '⚠️'
FAIL  = '❌'
SEP   = '`' + '-'*36 + '`'

def fetch(gid):
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={gid}'
    r = requests.get(url, timeout=15)
    r.encoding = 'utf-8'
    return list(csv.DictReader(io.StringIO(r.text)))

def money(s):
    if not s: return 0.0
    return float(s.replace('R$ ', '').replace(',', '.').strip() or 0)

def num(s):
    try: return int(str(s or '0').strip() or 0)
    except: return 0

def short(d):
    if not d: return ''
    p = d.split('/')
    return f"{p[0].zfill(2)}/{p[1].zfill(2)}" if len(p) >= 2 else d

def agg(rows):
    inv=clk=imp=lp=lp_clk=leads=0
    for r in rows:
        inv    += money(r.get('Investido', ''))
        clk    += num(r.get('Cliques', ''))
        imp    += num(r.get('Impressoes', ''))
        leads  += num(r.get('Leads', ''))
        has_lp  = bool((r.get('Visualizacoes_LP') or '').strip())
        lp     += num(r.get('Visualizacoes_LP', '')) if has_lp else 0
        lp_clk += num(r.get('Cliques', ''))          if has_lp else 0
    return dict(inv=inv, clk=clk, imp=imp, lp=lp, lp_clk=lp_clk, leads=leads)

def send(content):
    payload = json.dumps({'content': content}, ensure_ascii=False).encode('utf-8')
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    r = requests.post(WEBHOOK, data=payload, headers=headers, timeout=10)
    print(f"Discord {r.status_code}")

def main():
    now   = datetime.now(BR_TZ)
    today = now.strftime('%d/%m')

    eb_rows  = fetch('734559877')
    cap_rows = fetch('280005977')
    ld_rows  = fetch('1704118724')

    eb_hoje  = [r for r in eb_rows  if short(r.get('Date', '')) == today]
    cap_hoje = [r for r in cap_rows if short(r.get('Date', '')) == today]

    if not eb_hoje and eb_rows:
        dates = sorted({short(r.get('Date', '')) for r in eb_rows if r.get('Date', '')},
                       key=lambda x: (int(x.split('/')[1]), int(x.split('/')[0])))
        latest = dates[-1] if dates else ''
        eb_hoje  = [r for r in eb_rows  if short(r.get('Date', '')) == latest]
        cap_hoje = [r for r in cap_rows if short(r.get('Date', '')) == latest]
        today = latest

    eb  = agg(eb_hoje)
    cap = agg(cap_hoje)

    inv    = eb['inv']    + cap['inv']
    clk    = eb['clk']    + cap['clk']
    imp    = eb['imp']    + cap['imp']
    lp     = eb['lp']     + cap['lp']
    lp_clk = eb['lp_clk'] + cap['lp_clk']

    # Leads diarios (delta aba Leads)
    ld_data = []
    for r in ld_rows:
        vals = list(r.values())
        o = num(r.get('Leads Captação Org') or r.get('Leads Captacao Org') or (vals[1] if len(vals) > 1 else 0))
        c = num(r.get('Leads Captação Ads') or r.get('Leads Captacao Ads') or (vals[2] if len(vals) > 2 else 0))
        e = num(r.get('Ebook Ads') or (vals[3] if len(vals) > 3 else 0))
        d = short(r.get('Data', '') or (vals[0] if vals else ''))
        if any([o, c, e]):
            ld_data.append((d, o, c, e))

    prev_o = prev_c = prev_e = 0
    day_org = day_cap = day_eb = 0
    tot_org = tot_cap = tot_eb = 0
    for d, o, c, e in ld_data:
        if d == today:
            day_org = max(0, o - prev_o)
            day_cap = max(0, c - prev_c)
            day_eb  = max(0, e - prev_e)
        prev_o, prev_c, prev_e = o, c, e
        tot_org, tot_cap, tot_eb = o, c, e

    leads_dia   = day_eb + day_cap + day_org
    total_leads = tot_eb + tot_cap + tot_org

    cpa  = inv / leads_dia        if leads_dia > 0 else 0
    cpm  = inv / imp * 1000       if imp > 0       else 0
    ctr  = clk / imp * 100        if imp > 0       else 0
    cr   = lp  / lp_clk * 100    if lp_clk > 0   else 0
    conv = (eb['leads'] + cap['leads']) / lp * 100 if lp > 0 else 0

    days_left = max(1, (CAMP_END.replace(tzinfo=None) - now.replace(tzinfo=None)).days)
    needed    = max(0, round((550 + 750 + 1000 - total_leads) / days_left, 1))

    pct_leads = leads_dia / META_LEADS_DIA * 100
    pct_inv   = inv / META_INV_DIA * 100 if META_INV_DIA else 0
    cpa_meta  = META_INV_DIA / META_LEADS_DIA if META_LEADS_DIA else 0
    pct_cpa   = cpa / cpa_meta * 100 if cpa_meta > 0 else 0

    icon_l = OK   if pct_leads >= 90 else WARN if pct_leads >= 50 else FAIL
    icon_i = OK   if pct_inv   <= 105 else WARN
    icon_c = OK   if pct_cpa   <= 110 else FAIL

    if pct_leads >= 90:
        leitura = f"Meta de leads batida! Campanha no ritmo certo."
    elif pct_leads >= 50:
        leitura = f"Verba usada ({pct_inv:.0f}%), leads abaixo da meta ({pct_leads:.0f}%). CPA acima do esperado."
    else:
        leitura = f"Performance abaixo: {leads_dia} de {META_LEADS_DIA} leads previstos ({pct_leads:.0f}%). Revisar criativos."

    msg1 = '\n'.join([
        f"{BOOK} **DIARIO DE BORDO – CAPTACAO**",
        "**SEGUNDA RENDA INTERNACIONAL**",
        f"{CAL} **Data:** {now.strftime('%d/%m/%Y')}  {CLK} **Fechamento do dia**",
        "",
        SEP,
        f"{CHART} **RESULTADOS GERAIS – DIA {today}**",
        SEP,
        f"{TICK} **Leads captados no dia:** {leads_dia}  *(EB: {day_eb} | Cap: {day_cap} | Org: {day_org})*",
        f"{CASH} **Investimento do dia:** R$ {inv:.2f}",
        f"{CHART} **CPA do dia:** R$ {cpa:.2f}",
        f"{CHART} **CPM:** R$ {cpm:.2f}",
        f"{CHART} **CTR:** {ctr:.2f}%",
        f"{CHART} **Conversao de pagina:** {conv:.2f}%",
        f"{CHART} **Connect Rate:** {cr:.2f}%",
        f"{TICK} **Total de leads capturados:** {total_leads}  *(EB: {tot_eb} | Cap: {tot_cap} | Org: {tot_org})*",
    ])

    msg2 = '\n'.join([
        SEP,
        f"{CHART} **COMPARATIVO META DO DIA vs REALIZADO**",
        SEP,
        "```",
        f"{'Metrica':<14} {'Meta':>10}   {'Realizado':>10}   Ating.",
        f"{'Investimento':<14} R${META_INV_DIA:>8.2f}   R${inv:>8.2f}   {pct_inv:.0f}%",
        f"{'Leads':<14} {META_LEADS_DIA:>10}   {leads_dia:>10}   {pct_leads:.0f}%",
        f"{'CPA':<14} R${cpa_meta:>8.2f}   R${cpa:>8.2f}   {pct_cpa:.0f}%",
        "```",
        f"{PIN} **Leitura direta:**",
        f"{PTR} {leitura}",
        "",
        f"{HOUR} **Necessario/dia para bater meta:** **{needed} leads/dia** nos proximos {days_left} dias",
        f"{LINK} [Ver Dashboard](https://cardo-jpg.github.io/sri-dashboard-maio/)",
    ])

    msg3 = '\n'.join([
        SEP,
        f"{PIN} **OBSERVACAO DO DIA**",
        SEP,
        "> *[Gestor: descreva o que foi observado no dia]*",
        "",
        SEP,
        f"{DART} **DECISOES TOMADAS**",
        SEP,
        "> *[Gestor: liste as decisoes tomadas hoje]*",
        "",
        SEP,
        f"{MAG} **ACOES PARA AMANHA**",
        SEP,
        "> *[Gestor: liste as acoes prioritarias para o proximo dia]*",
    ])

    send(msg1)
    send(msg2)
    send(msg3)

if __name__ == '__main__':
    main()