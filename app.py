"""Presentation layer only. Calculation rules remain in calculator_engine.py."""
import math
import streamlit as st
from calculator_engine import DAILY_LOSS_LIMIT, MAINTENANCE_MARGIN_RATE, MARKETS, MAX_RISK_PER_TRADE, calculate

st.set_page_config(page_title="Position Size Calculator", page_icon="P", layout="wide")

def style():
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp{background:#f4f7fb;color:#10234a}.block-container{max-width:1440px;padding-top:1.5rem}
    html,body,[class*=css]{font-family:Inter,sans-serif}h1,h2,h3{color:#10234a!important}
    h1{font-size:1.7rem!important;margin-bottom:.1rem!important}
    [data-testid=stVerticalBlockBorderWrapper]{background:#fff;border:1px solid #dde5f1;border-radius:12px;box-shadow:0 4px 14px rgba(29,63,120,.05)}
    [data-testid=stVerticalBlockBorderWrapper]>div{padding:1rem 1.1rem}
    [data-testid=stMetric]{background:#f8faff;border:1px solid #e1e8f4;border-radius:10px;padding:.7rem}
    [data-testid=stMetricLabel]{color:#526784;font-size:.77rem;font-weight:600}
    [data-testid=stMetricValue]{color:#10234a;font-size:1.2rem;font-weight:700}
    /* Keep every form label and entered value readable on white surfaces. */
    label, label p, [data-testid=stWidgetLabel] p, [data-testid=stWidgetLabel] div,
    [data-testid=stSelectbox] label p, [data-testid=stRadio] label p,
    [data-testid=stToggle] label p, [data-testid=stExpander] summary p {color:#10234a!important;opacity:1!important}
    [data-testid=stNumberInput] input, [data-testid=stTextInput] input,
    [data-testid=stSelectbox] div[role=combobox], [data-baseweb=select] input {
        color:#10234a!important;background:#fff!important;-webkit-text-fill-color:#10234a!important;
    }
    [data-testid=stNumberInput] input::placeholder, [data-testid=stTextInput] input::placeholder {
        color:#7588a5!important;-webkit-text-fill-color:#7588a5!important;opacity:1!important;
    }
    [data-testid=stNumberInput] button, [data-testid=stSelectbox] svg {color:#244a86!important;fill:#244a86!important}
    div[data-testid=stButton]>button{background:#1f62dd;color:#fff;border:0;border-radius:9px;font-weight:700;min-height:2.75rem}
    div[data-testid=stButton]>button:hover{background:#174fab;color:#fff}
    .sub{color:#617490;font-size:.86rem;margin-top:-.25rem}.pill{display:inline-block;padding:.32rem .62rem;border-radius:999px;font-size:.78rem;font-weight:700}
    .long{color:#0d6b3a;background:#ddf6e7}.short{color:#a52b35;background:#fee8e9}
    .hero{background:linear-gradient(135deg,#102d61,#1f62bb);border-radius:12px;color:#fff;padding:1.15rem 1.2rem;margin-bottom:1rem}
    .hero p{margin:0;color:#dbe9ff;font-size:.8rem}.hero .value{font-size:2rem;font-weight:700;line-height:1.2}
    .empty{border:1px dashed #bfcee4;background:#f8faff;border-radius:12px;padding:4rem 1rem;text-align:center;color:#5e7190}.empty strong{display:block;color:#10234a;margin-bottom:.3rem}
    @media (max-width:700px){
      .st-key-mobile_nav{display:block!important}
      .st-key-main_grid [data-testid=stHorizontalBlock]{flex-direction:column!important;gap:1rem!important}
      .st-key-main_grid [data-testid=column]{width:100%!important;min-width:100%!important;flex:1 1 100%!important}
      .st-key-main_grid [data-testid=stDataFrame]{max-width:100%;overflow-x:auto}
      .block-container{padding-left:.8rem;padding-right:.8rem}
    }
    @media (min-width:701px){.st-key-mobile_nav{display:none!important}}
    </style>""", unsafe_allow_html=True)

def money(value): return "$" + format(value, ",.2f")
def fmt_price(value): return format(value, ",.8f").rstrip("0").rstrip(".")
def label(key): return MARKETS[key]["name"]
def heading(title, subtitle):
    st.subheader(title)
    st.markdown(f'<p class="sub">{subtitle}</p>', unsafe_allow_html=True)
def direction(entry, stop):
    if entry is None or stop is None: return "--"
    return "LONG" if stop < entry else "SHORT"
def signature(values): return repr(values)

def trade_setup():
    with st.container(border=True):
        heading("Trade setup", "Select your market and enter the trade details.")
        key = st.selectbox("Market", list(MARKETS), format_func=label)
        market = MARKETS[key]
        a,b = st.columns([3,1])
        balance = a.number_input("Account balance ($)", min_value=.01, value=None, placeholder="e.g. 10000", step=100.0)
        entry_col,stop_col,lev_col = st.columns(3)
        entry = entry_col.number_input("Entry price", min_value=.00000001, value=None, placeholder="e.g. 1.1050", format="%.8f", key="entry")
        stop = stop_col.number_input("Stop-loss price", min_value=.00000001, value=None, placeholder="e.g. 1.1000", format="%.8f", key="stop")
        trade_direction = direction(entry, stop)
        b.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
        direction_class = "long" if trade_direction == "LONG" else "short"
        b.markdown(f'<span class="pill {direction_class}">{trade_direction}</span>', unsafe_allow_html=True)
        leverage = 1.0
        if market["leveraged"]:
            leverage = lev_col.number_input("Leverage (1: value)", min_value=1.0, value=None, placeholder="e.g. 100", step=1.0)
        else:
            lev_col.caption("Unleveraged market (1:1)")
        conversion = None
        if market["quote"] in ("cross_direct","cross_inverse"):
            hint = "EURGBP: enter GBPUSD" if market["quote"] == "cross_direct" else "EURJPY: enter USDJPY"
            conversion = st.number_input("USD conversion-pair price", min_value=.00000001, value=None, placeholder="e.g. 1.2500", format="%.8f", help=hint)
            st.caption(hint)
    return key,market,balance,entry,stop,leverage,conversion

def risk_controls(balance):
    with st.container(border=True):
        heading("Risk controls", "Define the amount this trade is allowed to lose.")
        a,b=st.columns(2)
        risk=a.number_input("Risk per trade (%)",min_value=.01,max_value=100.0,value=1.0,step=.1)
        today=b.number_input("Loss already taken today ($)",min_value=0.0,value=0.0,step=10.0)
        with st.expander("Advanced risk limits"):
            a,b=st.columns(2)
            cap_mode=a.radio("Maximum risk mode",("Automatic","Custom"),horizontal=True)
            cap_pct=a.number_input("Automatic maximum risk (%)",min_value=.01,max_value=100.0,value=1.0,step=.1,disabled=cap_mode!="Automatic")
            cap_custom=a.number_input("Custom maximum risk ($)",min_value=.01,value=None,placeholder="e.g. 100",disabled=cap_mode!="Custom")
            daily_mode=b.radio("Daily loss limit mode",("Automatic","Custom"),horizontal=True)
            daily_pct=b.number_input("Automatic daily limit (%)",min_value=.01,max_value=100.0,value=3.0,step=.1,disabled=daily_mode!="Automatic")
            daily_custom=b.number_input("Custom daily loss limit ($)",min_value=.01,value=None,placeholder="e.g. 300",disabled=daily_mode!="Custom")
            maintenance=st.number_input("Maintenance margin assumption (%)",min_value=0.0,max_value=99.0,value=MAINTENANCE_MARGIN_RATE*100,step=.1)
            automatic_cap=None if balance is None else balance*cap_pct/100
            automatic_daily=None if balance is None else balance*daily_pct/100
            a.caption("Automatic cap: " + ("Enter balance" if automatic_cap is None else money(automatic_cap)))
            b.caption("Automatic daily limit: " + ("Enter balance" if automatic_daily is None else money(automatic_daily)))
    cap=automatic_cap if cap_mode=="Automatic" else cap_custom
    daily=automatic_daily if daily_mode=="Automatic" else daily_custom
    return risk,today,cap,daily,maintenance,cap_mode,daily_mode

def take_profit_plan(entry,stop):
    with st.container(border=True):
        heading("Take-profit plan", "Set one to three targets and choose how to close the position.")
        count=st.radio("Number of targets",(1,2,3),horizontal=True)
        mode=st.radio("Target method",("R Multiple (recommended)","Manual price"),horizontal=True)
        a,b,c=st.columns([1,2,2]);a.markdown("**Target**");b.markdown("**R multiple / price**");c.markdown("**Allocation**")
        targets=[]
        for index in range(count):
            a,b,c=st.columns([1,2,2]);a.markdown(f"**TP{index+1}**")
            r_multiple=None
            if mode.startswith("R Multiple"):
                r_multiple=b.number_input(f"TP{index+1} R multiple",min_value=.01,value=None,placeholder=f"e.g. {index+1}",step=.1,key=f"tp_r_{index}",label_visibility="collapsed")
                target=None if entry is None or stop is None or r_multiple is None else entry+(abs(entry-stop)*r_multiple if entry>stop else -abs(entry-stop)*r_multiple)
                b.caption("Target: --" if target is None else f"Target: {fmt_price(target)}")
            else:
                target=b.number_input(f"TP{index+1} price",min_value=.00000001,value=None,placeholder="e.g. 1.1100",format="%.8f",key=f"tp_price_{index}",label_visibility="collapsed")
            pct=c.number_input(f"TP{index+1} allocation",min_value=.01,max_value=100.0,value=None,placeholder="e.g. 50",step=1.0,key=f"tp_pct_{index}",label_visibility="collapsed")
            targets.append((target,pct,r_multiple))
        move=True if count==1 else st.toggle("Move remaining stop to break-even after TP1",value=True)
        st.caption("Enter an allocation for every target. Their total must equal 100%.")
    return targets,move,mode

def requirements(result):
    with st.container(border=True):
        heading("Trade requirements","Capital required for this trade setup.")
        cols=st.columns(3 if result["liquidation"] is not None else 2)
        cols[0].metric("Notional value",money(result["notional"]))
        cols[1].metric("Required margin",money(result["margin"]))
        if result["liquidation"] is not None: cols[2].metric("Est. liquidation",fmt_price(result["liquidation"]))

def results(result,market,balance,daily_enabled,target_rs):
    css="long" if result["direction"]=="LONG" else "short"
    st.markdown(f'<div class="hero"><p>CALCULATED POSITION SIZE</p><div class="value">{result["size"]:,.4f} {market["unit"]}</div><p><span class="pill {css}">{result["direction"]}</span></p></div>',unsafe_allow_html=True)
    a,b,c=st.columns(3)
    a.metric("Risk used",money(result["dollar_risk"]))
    b.metric("Actual stop loss",money(result["actual_loss"]),f"{result['actual_loss']/balance*100:.2f}% account")
    c.metric("Risk cap applied","Yes" if result["capped_by"] else "No")
    if result["capped_by"]: st.warning("Risk capped by " + " and ".join(result["capped_by"]) + ".")
    requirements(result)
    with st.container(border=True):
        heading("Take-profit breakdown","Estimated results after the engine's fee assumptions.")
        st.dataframe([{"Target":f"TP{i}","Price":fmt_price(s["price"]),"Allocation":f"{s['pct']:g}% | {s['size']:,.4f} {market['unit']}","Planned R":f"{target_rs[i-1]:g}R" if target_rs[i-1] is not None else f"{s['r']:.2f}R","Est. net profit":money(s["profit"])} for i,s in enumerate(result["stages"],1)],hide_index=True,width="stretch")
    with st.container(border=True):
        heading("Outcome scenarios","Net outcome after fees for each possible path.")
        st.dataframe([{"Scenario":name,"Net outcome":money(amount),"Status":"Profit" if amount>=0 else "Loss"} for name,amount in result["scenarios"]],hide_index=True,width="stretch")
    with st.container(border=True):
        heading("Performance metrics","Useful risk and expectancy reference points.")
        a,b,c=st.columns(3);a.metric("Blended R:R",f"1:{result['blended_rr']:.2f}")
        b.metric("Break-even win rate","N/A" if result["breakeven"] is None else f"{result['breakeven']:.1f}%")
        c.metric("Stop-outs remaining" if daily_enabled else "Fees, all targets",str(result["stopouts_to_limit"]) if daily_enabled else money(result["fees_all_hit"]))

def validation(balance,risk,entry,stop,leverage,conversion,market,targets,cap,daily,mode):
    errors=[]
    required={"Account balance":balance,"Risk per trade":risk,"Entry price":entry,"Stop-loss price":stop}
    if market["leveraged"]: required["Leverage"]=leverage
    if market["quote"] in ("cross_direct","cross_inverse"): required["USD conversion-pair price"]=conversion
    required["Maximum risk"]=cap
    required["Daily loss limit"]=daily
    for name,value in required.items():
        if value is None: errors.append(f"{name} is required.")
    for index,(target,pct,r_multiple) in enumerate(targets,1):
        if target is None: errors.append(f"TP{index} price is required.")
        if pct is None: errors.append(f"TP{index} allocation is required.")
    if errors: return errors
    if math.isclose(entry,stop): errors.append("Entry and stop-loss prices cannot be the same.")
    long=stop<entry; previous=entry; previous_r=0
    for i,(target,pct,r_multiple) in enumerate(targets,1):
        if (long and target<=previous) or (not long and target>=previous): errors.append(f"TP{i} must be further into profit than the previous price.")
        if mode.startswith("R Multiple") and (r_multiple is None or r_multiple<=previous_r): errors.append("R multiples must be positive and progressively increase.")
        previous_r=r_multiple if r_multiple is not None else previous_r
        if pct<=0: errors.append(f"TP{i} allocation must be greater than 0%.")
        previous=target
    if not math.isclose(sum(pct for _,pct,_ in targets),100.0,abs_tol=1e-6): errors.append("Take-profit allocations must total exactly 100%.")
    return errors

def warnings(result,risk,balance):
    messages=[]
    if risk>5: messages.append("Risk above 5% per trade is dangerous.")
    if result["size"]<=0: messages.append("Minimum volume step is larger than this risk budget. Widen risk or skip this trade.")
    if result["margin"]>balance: messages.append("Required margin is greater than your account balance.")
    if result["liq_before_stop"]: messages.append("Estimated liquidation is at or before your stop loss. Lower leverage.")
    for message in messages: st.warning(message)
    st.caption("Spread, funding, and slippage are not included.")

def main():
    style();st.title("Position Size Calculator");st.markdown('<p class="sub">A focused trade-planning tool built on your existing calculation engine.</p>',unsafe_allow_html=True);st.divider()
    with st.container(key="mobile_nav"):
        mobile_view=st.radio("View",("Inputs","Results"),horizontal=True,label_visibility="collapsed")
    if mobile_view=="Inputs":
        st.markdown("<style>@media(max-width:700px){.st-key-results_panel{display:none!important}}</style>",unsafe_allow_html=True)
    else:
        st.markdown("<style>@media(max-width:700px){.st-key-inputs_panel{display:none!important}}</style>",unsafe_allow_html=True)
    with st.container(key="main_grid"):
        left,right=st.columns([1.28,1],gap="large")
        with left:
            with st.container(key="inputs_panel"):
                key,market,balance,entry,stop,leverage,conversion=trade_setup()
                risk,today,cap,daily,maintenance,cap_mode,daily_mode=risk_controls(balance)
                targets,move,target_mode=take_profit_plan(entry,stop)
                pressed=st.button("Calculate position size",type="primary",width="stretch")
    engine_targets=[(target,pct) for target,pct,_ in targets]
    target_rs=[r for _,_,r in targets]
    inputs=(key,balance,risk,entry,stop,tuple(targets),conversion,leverage,cap,daily,maintenance,today,move,target_mode)
    current=signature(inputs)
    if pressed:
        errors=validation(balance,risk,entry,stop,leverage,conversion,market,targets,cap,daily,target_mode)
        if errors: st.session_state.pop("result",None);st.session_state["error"]=errors
        else:
            try:
                st.session_state["result"]=calculate(market,balance,risk,entry,stop,engine_targets,conv_rate=conversion,leverage=leverage,max_risk_per_trade=cap,daily_limit=daily,loss_today=0.0 if today is None else today,move_sl_to_be=move,maintenance_margin_rate=maintenance/100)
                st.session_state["target_rs"]=target_rs
                st.session_state.pop("error",None)
            except ValueError as error: st.session_state.pop("result",None);st.session_state["error"]=[str(error)]
        st.session_state["signature"]=current
    with right:
        with st.container(key="results_panel"):
            st.subheader("Calculation results");st.markdown('<p class="sub">Position size, risk, and trade outcomes.</p>',unsafe_allow_html=True)
            fresh=st.session_state.get("signature")==current
            if st.session_state.get("error") and fresh:
                for error in st.session_state["error"]:st.error(error)
            if st.session_state.get("result") and fresh:
                results(st.session_state["result"],market,balance,True,st.session_state.get("target_rs",target_rs));warnings(st.session_state["result"],risk,balance)
            else:
                text="Inputs changed. Recalculate to refresh every result." if st.session_state.get("result") or st.session_state.get("error") else "Enter your trade details, then calculate position size."
                st.markdown(f'<div class="empty"><strong>Awaiting calculation</strong>{text}</div>',unsafe_allow_html=True)
if __name__=="__main__": main()
