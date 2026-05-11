import requests, csv, io, os
from datetime import datetime, timedelta
import pytz

SHEET_ID = '1MNmYN39x8FB8BGBQocZGAL8kDGQ4WZ5B7uAy5KazJ1c'
WEBHOOK  = os.environ.get('DISCORD_WEBHOOK',
           'https://discord.com/api/webhooks/1503448814189809734/XeNe5njFg4CK_z0YUgKncxMNZVl_6W2li-yB1wfQgsVFE1nJfKIyY1JrA4p0V4AhHaVe')
BR_TZ    = pytz.timezone('America/Sao_Paulo')

META_LEADS_DIA = 40
META_INV_DIA   = 60.0   # R$/dia (ajuste conforme orçamento)
CAMP_END       = datetime(2026, 5, 30, tzinfo=pytz.utc)

def fetch(gid):
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={gid}'
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
    p = d.split('/')
    return f"{p[0].zfill(2)}/{p[1].zfill(2)}" if len(p) >= 2 else d

def agg(rows):
    inv=clk=imp=lp=lp_clk=leads=0
    for r in rows:
        inv    += money(r.get('Investido',''))
        clk    += num(r.get('Cliques',''))
        imp    += num(r.get('Impressoes',''))
        leads  += num(r.get('Leads',''))
        has_lp  = bool((r.get('Visualizacoes_LP') or '').strip())
        lp     += num(r.get('Visualizacoes_LP','')) if has_lp else 0
        lp_clk += num(r.get('Cliques',''))          if has_lp else 0
    return dict(inv=inv, clk=clk, imp=imp, lp=lp, lp_clk=lp_clk, leads=leads)

def send(content):
    r = requests.post(WEBHOOK, json={'content': content}, timeout=10)
    print(f"Discord {r.status_code}")

def main():
    now   = datetime.now(BR_TZ)
    today = now.strftime('%d/%m')

    eb_rows  = fetch('734559877')
    cap_rows = fetch('280005977')
    ld_rows  = fetch('1704118724')

    # Dados do dia (ou data mais recente)
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

    inv   = eb['inv']    + cap['inv']
    clk   = eb['clk']    + cap['clk']
    imp   = eb['imp']    + cap['imp']
    lp    = eb['lp']     + cap['lp']
    lp_clk= eb['lp_clk'] + cap['lp_clk']

    # Leads diários (delta da aba Leads)
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
    total_leads = tot_eb + tot_cap + tot_org

    # Métricas
    cpa  = inv/leads_dia        if leads_dia > 0 else 0
    cpm  = inv/imp*1000         if imp > 0       else 0
    ctr  = clk/imp*100          if imp > 0       else 0
    cr   = lp/lp_clk*100        if lp_clk > 0   else 0
    conv = leads_dia/lp*100     if lp > 0        else 0   # conversão de página

    days_left = max(1,(CAMP_END.replace(tzinfo=None)-now.replace(tzinfo=None)).days)

    # % atingimento
    pct_leads = leads_dia/META_LEADS_DIA*100
    pct_inv   = inv/META_INV_DIA*100 if META_INV_DIA else 0
    cpa_meta  = META_INV_DIA/META_LEADS_DIA if META_LEADS_DIA else 0
    pct_cpa   = cpa/cpa_meta*100 if cpa_meta > 0 else 0

    icon_l = '✅' if pct_leads>=90 else '⚠️' if pct_leads>=50 else '❌'
    icon_i = '✅' if pct_inv<=105 else '⚠️'
    icon_c = '✅' if pct_cpa<=110 else '❌'

    # Leitura direta automática
    if pct_leads >= 90:
        leitura = "Meta de leads batida! Campanha no ritmo certo."
    elif pct_leads >= 50:
        leitura = f"Verba utilizada ({pct_inv:.0f}%), mas leads abaixo da meta ({pct_leads:.0f}%). CPA acima do esperado."
    else:
        leitura = f"Performance abaixo do esperado: {leads_dia} leads de {META_LEADS_DIA} previstos ({pct_leads:.0f}%). Revisar criativos e segmentação."

    # ── MENSAGEM 1 — Resultados ──────────────────────────────────────────
    msg1 = f"""📘 **DIÁRIO DE BORDO – CAPTAÇÃO**
**SEGUNDA RENDA INTERNACIONAL**
📅 **Data:** {now.strftime('%d/%m/%Y')}  ⏰ **Fechamento do dia**

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **RESULTADOS GERAIS – DIA {today}**
━━━━━━━━━━━━━━━━━━━━━━━━
🎟 **Leads captados no dia:** {leads_dia} _(EB: {day_eb} | Cap: {day_cap} | Org: {day_org})_
💰 **Investimento do dia:** R$ {inv:.2f}
📊 **CPA do dia:** R$ {cpa:.2f}
📊 **CPM:** R$ {cpm:.2f}
📊 **CTR:** {ctr:.2f}%
📊 **Conversão de página:** {conv:.2f}%
📊 **Connect Rate:** {cr:.2f}%
🎟 **Total de leads capturados:** {total_leads} _(EB: {tot_eb} | Cap: {tot_cap} | Org: {tot_org})_"""

    # ── MENSAGEM 2 — Comparativo + Leitura ──────────────────────────────
    msg2 = f"""━━━━━━━━━━━━━━━━━━━━━━━━
📊 **COMPARATIVO META DO DIA vs REALIZADO**
━━━━━━━━━━━━━━━━━━━━━━━━
```
Métrica        Meta            Realizado       Ating.
Investimento   R$ {META_INV_DIA:.2f}       R$ {inv:.2f}      {pct_inv:.0f}% {icon_i}
Leads          {META_LEADS_DIA}              {leads_dia}              {pct_leads:.0f}% {icon_l}
CPA            R$ {cpa_meta:.2f}        R$ {cpa:.2f}       {pct_cpa:.0f}% {icon_c}
```
📌 **Leitura direta:**
👉 {leitura}

⏳ **Necessário/dia para bater meta:** {(max(0,(tot_eb+tot_cap+tot_org-0))):} leads acumulados · ainda precisam entrar **{max(0, round((550+750+1000 - total_leads)/days_left, 1))}** leads/dia nos próximos {days_left} dias
🔗 [Ver Dashboard completo](https://cardo-jpg.github.io/sri-dashboard-maio/)"""

    # ── MENSAGEM 3 — Seções narrativas (a preencher) ────────────────────
    msg3 = f"""━━━━━━━━━━━━━━━━━━━━━━━━
📌 **OBSERVAÇÃO DO DIA**
━━━━━━━━━━━━━━━━━━━━━━━━
> _[Gestor: descreva aqui o que foi observado e tentado durante o dia]_

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **DECISÕES TOMADAS**
━━━━━━━━━━━━━━━━━━━━━━━━
> _[Gestor: liste as decisões tomadas hoje]_

━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **AÇÕES PARA AMANHÃ**
━━━━━━━━━━━━━━━━━━━━━━━━
> _[Gestor: liste as ações prioritárias para o próximo dia]_"""

    send(msg1)
    send(msg2)
    send(msg3)

if __name__ == '__main__':
    main()