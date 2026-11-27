import streamlit as st
import json
from white_lion_orchestrator import WhiteLionOrchestrator

st.set_page_config(page_title="White Lion War Room", page_icon="🦁", layout="wide")
st.title("🦁 غرفة عمليات الأسد الأبيض (White Lion)")
st.markdown("**القائد:** ALASD ALABIYD | **النظام:** Sovereign Fortress")

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = WhiteLionOrchestrator()
if "plan" not in st.session_state:
    st.session_state.plan = None
if "results" not in st.session_state:
    st.session_state.results = []

with st.sidebar:
    st.header("⚙️ حالة النظام")
    if st.button("🔄 مسح الجلسة (Reset)"):
        st.session_state.plan = None
        st.session_state.results = []
        st.rerun()

goal = st.text_area("🎯 أدخل الهدف الاستراتيجي هنا:", height=100, placeholder="مثال: أطلق حملة لمتجر White Lion...")

if st.button("👑 1. تحليل الهدف (استدعاء القائد)", type="primary"):
    if not goal.strip():
        st.warning("الرجاء إدخال هدف أولاً.")
    else:
        with st.spinner("القائد يحلل الهدف ويوزع المهام..."):
            plan = st.session_state.orchestrator.run_commander(goal)
            if plan.get("status") == "error":
                st.error(f"فشل التخطيط: {plan.get('message')}")
            else:
                st.session_state.plan = plan
                st.session_state.results = []
                st.success("تم استلام خطة القائد بنجاح.")

if st.session_state.plan:
    st.subheader("📋 خطة العمليات (مخرجات القائد)")
    st.json(st.session_state.plan)
    
    if st.button("🚀 2. تنفيذ المهام (Execution Loop)", type="primary"):
        st.session_state.results = []
        tasks = st.session_state.plan.get("tasks", [])
        
        for i, task in enumerate(tasks):
            agent = task.get("agent")
            prompt = task.get("task")
            action = task.get("action", "generate")
            
            st.markdown(f"--- \n### ⚙️ المهمة {i+1}: {agent.upper()}")
            st.info(f"**الوصف:** {prompt}")
            
            if action in ["publish", "payment"]:
                st.warning(f"⚠️ هذه المهمة تتطلب إجراءً حساساً: {action}")
                approved = st.checkbox(f"أوافق على إجراء {action} للمهمة {i+1}", key=f"approve_{i}")
                if not approved:
                    st.error("❌ تم حظر المهمة: بانتظار الموافقة البشرية.")
                    st.session_state.results.append({"agent": agent, "status": "blocked", "message": "No human approval"})
                    continue
            
            with st.spinner(f"الوكيل {agent} يعمل..."):
                result = {}
                routes = {
                    "content": st.session_state.orchestrator.run_content_agent,
                    "marketing": st.session_state.orchestrator.run_marketing_agent,
                    "tech": st.session_state.orchestrator.run_tech_agent,
                    "teacher": st.session_state.orchestrator.run_teacher_agent,
                    "shopping": st.session_state.orchestrator.run_shopping_agent,
                }
                
                if agent in routes:
                    result = routes[agent](prompt)
                else:
                    result = {"status": "error", "message": f"وكيل غير معروف: {agent}"}
                
                st.session_state.results.append({"agent": agent, "task": prompt, **result})
                
                if result.get("status") == "success":
                    st.success("✅ تم التنفيذ بنجاح")
                    with st.expander("عرض المخرجات"):
                        st.write(result.get("content", ""))
                else:
                    st.error(f"❌ فشل التنفيذ: {result.get('message')}")

    if st.session_state.results:
        st.subheader("⚖️ تقرير المراجعة النهائي (المعلم)")
        for res in st.session_state.results:
            if res["agent"] == "teacher" and res.get("status") == "success":
                st.markdown(res.get("content", ""))
            elif res["agent"] == "teacher" and res.get("status") == "error":
                st.error(res.get("message"))
