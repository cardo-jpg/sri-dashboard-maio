import requests, csv, io, os, json
from datetime import datetime, timedelta
import pytz

SHEET_ID   = '1MNmYN39x8FB8BGBQocZGAL8kDGQ4WZ5B7uAy5KazJ1c'
SURVEY_ID  = '18wzuA-CjSiJpvVz3IS0SXf_JEDcXoL-YRTKVxYaMQ7c'
SURVEY_GID = '191514469'
WEBHOOK    = os.environ.get('DISCORD_WEBHOOK',
             'https://discord.com/api/webhooks/1503448814189809734/XeNe5njFg4CK_z0YUgKncxMNZVl_6W2li-yB1wfQgsVFE1nJfKIyY1JrA4p0V4AhHaVe')
BR_TZ      = pytz.timezone('America/Sao_Paulo')

META_LEADS_DIA = 40
META_INV_DIA   = 60.0
CPA_META       = 1.75   # media ebook 1.50 + captacao 2.00
CAMP_END       = datetime(2026, 5, 30, tzinfo=pytz.utc)

OK   = '✅'
WARN = '⚠️'
FAIL = '❌'
BOOK = '\U0001F4D8'
CAL  = '\U0001F4C5'
CHART= '\U0001F4CA'
TICK = '\U0001F39F'
CASH = '\U0001F4B0'
PIN  = '\U0001F4CC'
HOUR = '⏳'
LINK = '\U0001F517'
DART = '\U0001F3AF'
MAG  = '\U0001F50D'
STAR = '⭐'
SEP  = '`' + '─' * 34 + '`'

def fetch(gid, sid=SHEET_ID):
    url = f'https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv&gid={gid}'
    r = requests.get(url, timeout=15); r.encoding = 'utf-8'
    return list(csv.DictReader(io.StringIO(r.text)))

def money(s):
    if not s: return 0.0
    return float(s.replace('R$ ','').replace(',','.').strip() or 0)

def num(s):
    try: return int(str(s or '0').strip() or 0)
    except: return 0

def short(d):
    if not d: return ''
    p = d.split('/'); return f"{p[0].zfill(2)}/{p[1].zfill(2)}" if len(p)>=2 else d

def get_lp_val(r):
    # Tenta nome exato, depois busca parcial (LP, landing, visualiza)
    v = r.get('Visualizacoes_LP') or r.get('Visualizações_LP') or r.get('Visualizacoes LP') or ''
    if not v:
        v = next((val for k, val in r.items()
                  if any(x in k.lower() for x in ['visualiz','landing','_lp'])), '') or ''
    return str(v).strip()

def agg(rows):
    inv=clk=imp=lp=lp_clk=leads=0
    for r in rows:
        inv    += money(r.get('Investido',''))
        clk    += num(r.get('Cliques',''))
        imp    += num(r.get('Impressoes',''))
        leads  += num(r.get('Leads',''))
        lp_raw  = get_lp_val(r)
        has_lp  = bool(lp_raw)
        lp     += num(lp_raw) if has_lp else 0
        lp_clk += num(r.get('Cliques','')) if has_lp else 0
    return dict(inv=inv, clk=clk, imp=imp, lp=lp, lp_clk=lp_clk, leads=leads)

def connect_rate(a):
    return a['lp'] / a['lp_clk'] * 100 if a['lp_clk'] > 0 else 0

def mql_count(rows, date_str=None):
    total = mql = 0
    for r in rows:
        ts = r.get('Carimbo de data/hora', '')
        if date_str and date_str not in ts:
            continue
        eng = r.get('Voce fala ingles?', r.get(
              'Ù fala inglês?', next(
              (v for k,v in r.items() if 'ingl' in k.lower()), ''))).lower()
        sal = r.get('Qual a sua faixa salarial (não vamos divulgar essa informação)', next(
              (v for k,v in r.items() if 'salarial' in k.lower() or 'faixa' in k.lower()), '')).lower()
        total += 1
        fluent = 'confiante' in eng or 'fluente' in eng or 'fluent' in eng
        above2k = any(x in sal for x in ['3 a 5','5 a 10','acima','2 a 3','mais de 2',
                                          '10 mil','15 mil','20 mil'])
        if fluent and above2k:
            mql += 1
    return mql, total

def pct_icon(val, meta, higher_is_better=True):
    p = val / meta * 100 if meta else 0
    if higher_is_better:
        icon = OK if p >= 90 else WARN if p >= 50 else FAIL
    else:
        icon = OK if p <= 110 else WARN if p <= 140 else FAIL
    return p, icon

def send(content):
    payload = json.dumps({'content': content}, ensure_ascii=False).encode('utf-8')
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    r = requests.post(WEBHOOK, data=payload, headers=headers, timeout=10)
    print(f"Discord {r.status_code}")

def fmt_r(v): return f"R$ {v:.2f}".replace('.',',')

def main():
    now   = datetime.now(BR_TZ)
    today = now.strftime('%d/%m')
    yest  = (now - timedelta(days=1)).strftime('%d/%m/%Y')

    eb_rows  = fetch('734559877')
    cap_rows = fetch('280005977')
    ld_rows  = fetch('1704118724')
    sv_rows  = fetch(SURVEY_GID, SURVEY_ID)

    eb_hoje  = [r for r in eb_rows  if short(r.get('Date','')) == today]
    cap_hoje = [r for r in cap_rows if short(r.get('Date','')) == today]

    if not eb_hoje and eb_rows:
        dates = sorted({short(r.get('Date','')) for r in eb_rows if r.get('Date','')},
                       key=lambda x: (int(x.split('/')[1]), int(x.split('/')[0])))
        latest = dates[-1] if dates else ''
        eb_hoje  = [r for r in eb_rows  if short(r.get('Date','')) == latest]
        cap_hoje = [r for r in cap_rows if short(r.get('Date','')) == latest]
        today = latest

    eb  = agg(eb_hoje)
    cap = agg(cap_hoje)

    inv    = eb['inv']  + cap['inv']
    clk    = eb['clk']  + cap['clk']
    imp    = eb['imp']  + cap['imp']
    cr_eb  = connect_rate(eb)
    cr_cap = connect_rate(cap)

    # Leads diarios (delta aba Leads)
    ld_data = []
    for r in ld_rows:
        vals = list(r.values())
        o = num(r.get('Leads Captação Org') or r.get('Leads Captacao Org') or (vals[1] if len(vals)>1 else 0))
        c = num(r.get('Leads Captação Ads') or r.get('Leads Captacao Ads') or (vals[2] if len(vals)>2 else 0))
        e = num(r.get('Ebook Ads') or (vals[3] if len(vals)>3 else 0))
        d = short(r.get('Data','') or (vals[0] if vals else ''))
        if any([o,c,e]): ld_data.append((d,o,c,e))

    prev_o=prev_c=prev_e=0
    day_org=day_cap=day_eb=0
    tot_org=tot_cap=tot_eb=0
    for d,o,c,e in ld_data:
        if d == today:
            day_org=max(0,o-prev_o); day_cap=max(0,c-prev_c); day_eb=max(0,e-prev_e)
        prev_o,prev_c,prev_e=o,c,e
        tot_org,tot_cap,tot_eb=o,c,e

    leads_dia   = day_eb + day_cap + day_org
    paid_leads  = day_eb + day_cap          # so leads pagos para CPA
    total_leads = tot_eb + tot_cap + tot_org

    cpa  = inv / paid_leads     if paid_leads > 0 else 0
    cpm  = inv / imp * 1000     if imp > 0        else 0
    ctr  = clk / imp * 100      if imp > 0        else 0

    days_left = max(1,(CAMP_END.replace(tzinfo=None)-now.replace(tzinfo=None)).days)
    needed    = max(0, round((550+750+1000-total_leads)/days_left, 1))

    # Comparativo atingimento
    p_leads, i_leads = pct_icon(leads_dia, META_LEADS_DIA, higher_is_better=True)
    p_inv,   i_inv   = pct_icon(inv, META_INV_DIA,   higher_is_better=False)
    p_cpa,   i_cpa   = pct_icon(cpa, CPA_META,       higher_is_better=False)

    # MQL survey
    mql_hoje, tot_hoje   = mql_count(sv_rows, now.strftime('%d/%m/%Y'))
    mql_ontem, tot_ontem = mql_count(sv_rows, yest)
    mql_pct_hoje  = mql_hoje  / tot_hoje  * 100 if tot_hoje  else 0
    mql_pct_ontem = mql_ontem / tot_ontem * 100 if tot_ontem else 0
    mql_delta = mql_pct_hoje - mql_pct_ontem
    mql_icon  = OK if mql_delta >= 0 else WARN

    # MSG 1 — Resultados
    msg1 = '\n'.join([
        f"{BOOK} **DIARIO DE BORDO - CAPTACAO**",
        "**SEGUNDA RENDA INTERNACIONAL**",
        f"{CAL} **Data:** {now.strftime('%d/%m/%Y')}  |  Fechamento do dia",
        "",
        SEP,
        f"{CHART} **RESULTADOS GERAIS - DIA {today}**",
        SEP,
        f"{TICK} **Leads captados no dia:** {leads_dia}  *(EB: {day_eb} | Cap: {day_cap} | Org: {day_org})*",
        f"{CASH} **Investimento do dia:** {fmt_r(inv)}",
        f"{CHART} **CPA do dia:** {fmt_r(cpa)}",
        f"{CHART} **CPM:** {fmt_r(cpm)}",
        f"{CHART} **CTR:** {ctr:.2f}%",
        f"{CHART} **Connect Rate Ebook:** {cr_eb:.2f}%",
        f"{CHART} **Connect Rate Captacao:** {cr_cap:.2f}%",
        f"{STAR} **MQL do dia:** {mql_hoje} ({mql_pct_hoje:.1f}%)  {mql_icon}  *(ontem: {mql_ontem} / {mql_pct_ontem:.1f}%)*",
        "",
        f"{TICK} **Total de leads capturados:** {total_leads}  *(EB: {tot_eb} | Cap: {tot_cap} | Org: {tot_org})*",
    ])

    META_TOTAL = 550 + 750 + 1000
    faltam_dia = max(0, META_LEADS_DIA - leads_dia)
    faltam_tot = max(0, META_TOTAL - total_leads)
    pct_total  = round(total_leads / META_TOTAL * 100, 1)

    # MSG 2 — Comparativo + Progresso
    msg2 = '\n'.join([
        SEP,
        f"{CHART} **COMPARATIVO META DO DIA vs REALIZADO**",
        SEP,
        f"{i_inv}  **Invest:** {fmt_r(META_INV_DIA)} -> {fmt_r(inv)} **({p_inv:.0f}%)**",
        f"{i_leads}  **Leads:**  {META_LEADS_DIA} leads -> {leads_dia} leads **({p_leads:.0f}%)**",
        f"{i_cpa}  **CPA:**    {fmt_r(CPA_META)} -> {fmt_r(cpa)} **({p_cpa:.0f}%)**",
        "",
        SEP,
        f"{TICK} **PROGRESSO DA CAMPANHA**",
        SEP,
        f"{'📗'} **Ebook:**    {tot_eb:>4} / 550  ({round(tot_eb/550*100,1)}%)  |  Faltam **{max(0,550-tot_eb)}**",
        f"{'📙'} **Captacao:** {tot_cap:>4} / 750  ({round(tot_cap/750*100,1)}%)  |  Faltam **{max(0,750-tot_cap)}**",
        f"{'📕'} **Organico:** {tot_org:>4} / 1000 ({round(tot_org/1000*100,1)}%)  |  Faltam **{max(0,1000-tot_org)}**",
        f"**Total:**      {total_leads:>4} / {META_TOTAL} ({pct_total}%)  |  Faltam **{faltam_tot}**",
        f"{HOUR} Necessario: **{needed} leads/dia** nos proximos {days_left} dias",
        f"{LINK} [Dashboard](https://cardo-jpg.github.io/sri-dashboard-maio/)",
    ])

    # MSG 3 — Narrativa (gestor preenche)
    msg3 = '\n'.join([
        SEP,
        f"{PIN} **OBSERVACAO DO DIA**",
        SEP,
        "> ",
        "",
        SEP,
        f"{DART} **DECISOES TOMADAS**",
        SEP,
        "> ",
        "",
        SEP,
        f"{MAG} **ACOES PARA AMANHA**",
        SEP,
        "> ",
    ])

    send(msg1)
    send(msg2)
    send(msg3)

if __name__ == '__main__':
    main()