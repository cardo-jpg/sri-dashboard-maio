import requests, csv, io
from datetime import datetime, timedelta
import pytz

SHEET_ID  = '1MNmYN39x8FB8BGBQocZGAL8kDGQ4WZ5B7uAy5KazJ1c'
WEBHOOK   = 'https://discord.com/api/webhooks/1503448814189809734/XeNe5njFg4CK_z0YUgKncxMNZVl_6W2li-yB1wfQgsVFE1nJfKIyY1JrA4p0V4AhHaVe'
BR_TZ     = pytz.timezone('America/Sao_Paulo')

META_EB   = 550
META_CAP  = 750
META_ORG  = 1000
META_LEADS_DIA = 40
CAMP_END  = datetime(2026, 5, 30, tzinfo=pytz.utc)

def fetch(gid):
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={gid}'
    r = requests.get(url, timeout=15)
    r.encoding = 'utf-8'
    return list(csv.DictReader(io.StringIO(r.text)))

def money(s):
    if not s: return 0.0
    return float(s.replace('R$ ','').replace(',','.').strip() or 0)

def num(s):
    try: return int(s or 0)
    except: return 0

def short(d):
    if not d: return ''
    p = d.split('/')
    return f"{p[0].zfill(2)}/{p[1].zfill(2)}" if len(p) >= 2 else d

def agg(rows):
    inv=clk=imp=lp=lp_clk=0
    for r in rows:
        inv    += money(r.get('Investido',''))
        clk    += num(r.get('Cliques',''))
        imp    += num(r.get('Impressoes',''))
        has_lp  = bool((r.get('Visualizacoes_LP') or '').strip())
        lp     += num(r.get('Visualizacoes_LP','')) if has_lp else 0
        lp_clk += num(r.get('Cliques','')) if has_lp else 0
    return dict(inv=inv, clk=clk, imp=imp, lp=lp, lp_clk=lp_clk)

def main():
    now   = datetime.now(BR_TZ)
    today = now.strftime('%d/%m')

    eb_rows  = fetch('734559877')
    cap_rows = fetch('280005977')
    ld_rows  = fetch('1704118724')

    # Dados de hoje (ou data mais recente disponível)
    eb_today  = [r for r in eb_rows  if short(r.get('Date','')) == today]
    cap_today = [r for r in cap_rows if short(r.get('Date','')) == today]

    if not eb_today and eb_rows:
        dates = sorted({short(r.get('Date','')) for r in eb_rows if r.get('Date','')},
                       key=lambda x: (int(x.split('/')[1]), int(x.split('/')[0])))
        latest = dates[-1] if dates else ''
        eb_today  = [r for r in eb_rows  if short(r.get('Date','')) == latest]
        cap_today = [r for r in cap_rows if short(r.get('Date','')) == latest]
        today_label = latest
    else:
        today_label = today

    eb  = agg(eb_today)
    cap = agg(cap_today)

    inv_total = eb['inv'] + cap['inv']
    clk_total = eb['clk'] + cap['clk']
    imp_total = eb['imp'] + cap['imp']
    lp_total  = eb['lp']  + cap['lp']
    lpc_total = eb['lp_clk'] + cap['lp_clk']

    # Leads diários (delta acumulado aba Leads)
    ld_data = []
    for r in ld_rows:
        o = num(r.get('Leads Captação Org') or r.get('Leads Captacao Org') or list(r.values())[1] if len(r)>1 else 0)
        c = num(r.get('Leads Captação Ads') or r.get('Leads Captacao Ads') or list(r.values())[2] if len(r)>2 else 0)
        e = num(r.get('Ebook Ads') or list(r.values())[3] if len(r)>3 else 0)
        d = short(r.get('Data','') or list(r.values())[0] if r else '')
        if any([o,c,e]): ld_data.append((d,o,c,e))

    prev_o=prev_c=prev_e=0
    day_org=day_cap=day_eb=0
    tot_org=tot_cap=tot_eb=0
    for d,o,c,e in ld_data:
        if d == today_label:
            day_org=max(0,o-prev_o); day_cap=max(0,c-prev_c); day_eb=max(0,e-prev_e)
        prev_o,prev_c,prev_e=o,c,e
        tot_org,tot_cap,tot_eb=o,c,e

    leads_dia   = day_eb + day_cap + day_org
    total_leads = tot_eb + tot_cap + tot_org

    # Métricas
    cpa  = inv_total/leads_dia      if leads_dia  > 0 else 0
    cpm  = inv_total/imp_total*1000 if imp_total  > 0 else 0
    ctr  = clk_total/imp_total*100  if imp_total  > 0 else 0
    cr   = lp_total/lpc_total*100   if lpc_total  > 0 else 0

    days_left = max(1,(CAMP_END.replace(tzinfo=None)-now.replace(tzinfo=None)).days)
    pace_geral = max(0,(META_EB+META_CAP+META_ORG-total_leads)/days_left)

    pct_leads = leads_dia/META_LEADS_DIA*100 if META_LEADS_DIA else 0
    icon_leads = '✅' if pct_leads>=90 else '⚠️' if pct_leads>=50 else '❌'
    pct_inv   = inv_total/(META_EB+META_CAP)*100 if (META_EB+META_CAP) else 0

    # Embed Discord
    cor = 0x00e5a0 if pct_leads>=90 else 0xffd166 if pct_leads>=50 else 0xff6b6b

    embed = {
        "title": f"📘 Diário de Bordo · SRI Maio · {today_label}",
        "color": cor,
        "fields": [
            {"name": "🎟 Leads do dia",        "value": f"**{leads_dia}** (EB: {day_eb} | Cap: {day_cap} | Org: {day_org})", "inline": False},
            {"name": "💰 Investimento",         "value": f"R$ {inv_total:.2f}",      "inline": True},
            {"name": "📊 CPA",                  "value": f"R$ {cpa:.2f}",            "inline": True},
            {"name": "📊 CPM",                  "value": f"R$ {cpm:.2f}",            "inline": True},
            {"name": "📊 CTR",                  "value": f"{ctr:.2f}%",              "inline": True},
            {"name": "📊 Connect Rate",         "value": f"{cr:.2f}%",              "inline": True},
            {"name": "​",                  "value": "​",                   "inline": True},
            {"name": "🎟 Total acumulado",      "value": f"**{total_leads}** (EB: {tot_eb} | Cap: {tot_cap} | Org: {tot_org})", "inline": False},
            {"name": f"{icon_leads} Meta leads/dia",  "value": f"Meta: {META_LEADS_DIA} · Realizado: {leads_dia} · **{pct_leads:.0f}%**", "inline": False},
            {"name": "⏳ Necessário/dia (restante)", "value": f"**{pace_geral:.1f} leads/dia** para bater a meta até 30/05 ({days_left} dias)", "inline": False},
        ],
        "footer": {"text": "Sri Dashboard · Cardo Marketing"},
        "url": "https://cardo-jpg.github.io/sri-dashboard-maio/",
        "timestamp": now.isoformat()
    }

    resp = requests.post(WEBHOOK, json={"embeds": [embed]}, timeout=10)
    print(f"Discord: {resp.status_code} — {resp.text[:200]}")

if __name__ == '__main__':
    main()