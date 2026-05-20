/* ===== wizard.js =====
   排課精靈：現在會在完成條件設定後，將結果傳遞至新的 results.html 頁面。
*/

(function (win, doc) {
  const PRESET_SKILLS = {
    'AI 工程師': ['Python','TensorFlow','PyTorch','Machine Learning','Deep Learning','Pandas','NumPy','Scikit-learn','MLOps','Docker'],
    '資料工程師': ['Python','SQL','ETL','Airflow','Kafka','Spark','Hadoop','Data Warehouse','Docker','AWS'],
    '前端工程師': ['JavaScript','TypeScript','React','Vue.js','HTML','CSS','Tailwind','Webpack','REST API','Git'],
    '後端工程師': ['Java','Spring','Node.js','Express','Python','Django','Go','SQL','MySQL','Docker'],
    '全端工程師': ['JavaScript','TypeScript','React','Node.js','Express','SQL','Docker','Git','REST API','CI/CD'],
    'DevOps 工程師': ['Linux','Docker','Kubernetes','CI/CD','Jenkins','Terraform','Prometheus','Grafana','AWS','Shell'],
    '雲端架構師': ['AWS','Azure','GCP','Docker','Kubernetes','Terraform','CI/CD','Linux','Networking','Security'],
    'Mobile 工程師（iOS/Android）': ['Swift','Kotlin','Android','iOS','Flutter','React Native','REST API','MVVM','Xcode','Gradle'],
    '網路安全工程師': ['OWASP','Penetration Testing','SIEM','IDS/IPS','Network Security','Python','Burp Suite','Nmap','Kali Linux','Threat Modeling'],
    '數據分析師': ['SQL','Python','Pandas','Excel','Tableau','Power BI','Statistics','A/B Testing','Data Visualization','ETL'],
    '機器學習工程師': ['Python','Scikit-learn','TensorFlow','PyTorch','ML Ops','Feature Engineering','Model Serving','Docker','FastAPI','Kubernetes'],
  };

  // 工具函式
  function deriveSkillsFromCategories(cats) {
    const set = new Set();
    (cats || []).forEach(c => (PRESET_SKILLS[c] || []).forEach(s => set.add(s)));
    return Array.from(set).slice(0, 20);
  }
  function el(html){ const d=doc.createElement('div'); d.innerHTML=html.trim(); return d.firstElementChild; }
  function chipHTML(text, checked){
    return `<label class="chip ${checked?'active':''}" data-val="${text}">
      <input type="checkbox" ${checked?'checked':''}/>
      <span class="chip-text">${text}</span>
    </label>`;
  }

  const STEP_LABEL = s => ({1:'類別/目標', 2:'Dashboard', 3:'技能挑選', 4:'條件設定'})[s] || '';

  function buildWizard(init) {
    const state = Object.assign({
      categories: [],
      skills: [],
      hours: 0,
      budget: 0,
      durationMonths: 0,
      durationWeeks: 0,
      skipCategoryStep: false,
      startFromSkills: false,
    }, init || {});

    const root = el(`
    <div class="wiz-overlay" role="dialog" aria-modal="true">
      <div class="wiz-panel">
        <header class="wiz-header">
          <div class="wiz-title"><i class="fa-solid fa-magic"></i> 排課精靈</div>
          <button class="wiz-close" aria-label="關閉">&times;</button>
        </header>
        <div class="wiz-steps" id="wizSteps"></div>
        <main class="wiz-body"></main>
        <footer class="wiz-footer">
          <button class="btn" data-action="prev" disabled>上一步</button>
          <div class="wiz-gap"></div>
          <button class="btn" data-action="cancel">取消</button>
          <button class="btn-primary" data-action="next">下一步</button>
          <button class="btn-primary" data-action="finish" style="display:none;">完成設定</button>
        </footer>
      </div>
    </div>`);

    let visibleSteps;
    if (state.startFromSkills) {
      visibleSteps = [3, 4];
    } else if (state.skipCategoryStep) {
      visibleSteps = [2, 3, 4];
    } else {
      visibleSteps = [1, 2, 3, 4];
    }
    
    let index = 0;
    const actual = () => visibleSteps[index];

    const stepsEl = root.querySelector('#wizSteps');
    const body = root.querySelector('.wiz-body');
    const btnPrev = root.querySelector('[data-action="prev"]');
    const btnNext = root.querySelector('[data-action="next"]');
    const btnFinish = root.querySelector('[data-action="finish"]');
    const btnCancel = root.querySelector('[data-action="cancel"]');
    const btnClose = root.querySelector('.wiz-close');

    function renderStepsBar() {
      stepsEl.innerHTML = visibleSteps
        .map((s, i) => `<div class="wiz-step ${i === index ? 'active' : (i < index ? 'done' : '')}" data-i="${i}">
          <span>${i + 1}</span> ${STEP_LABEL(s)}
        </div>`).join('');
    }

    function renderStep() {
      renderStepsBar();
      const step = actual();

      btnPrev.onclick = () => { if (index > 0) { index--; renderStep(); } };
      btnNext.onclick = () => { if (index < visibleSteps.length - 1) { index++; renderStep(); } };

      btnPrev.disabled = index === 0;
      btnNext.style.display = (index === visibleSteps.length - 1) ? 'none' : '';
      btnFinish.style.display = (index === visibleSteps.length - 1) ? '' : 'none';
      
      // --- FIXED: 填入所有步驟的完整內容 ---
      if (step === 1) { 
        const base = state.categories.length ? state.categories : [
          'AI 工程師','資料工程師','前端工程師','後端工程師','全端工程師',
          '數據分析師','DevOps 工程師','雲端架構師','機器學習工程師','網路安全工程師'
        ];
        const selected = new Set(state.categories);
        body.innerHTML = `
          <section class="wiz-card">
            <h3 class="wiz-h3">確認或選擇你的目標職涯</h3>
            <p class="note">此步驟影響後續的預設技能建議</p>
            <div class="chip-wrap" id="catWrap">
              ${base.map(txt => chipHTML(txt, selected.has(txt))).join('')}
            </div>
          </section>`;

        const wrap = body.querySelector('#catWrap');
        wrap.querySelectorAll('label.chip').forEach(lab=>{
          const input = lab.querySelector('input');
          const sync = ()=> lab.classList.toggle('active', input.checked);
          sync();
          input.addEventListener('change', sync);
          lab.addEventListener('click', (e)=>{ if(e.target!==input){ e.preventDefault(); input.checked=!input.checked; sync(); }});
        });

        btnNext.onclick = ()=>{
          state.categories = [...wrap.querySelectorAll('label.chip input:checked')].map(i=>i.closest('label.chip').dataset.val);
          if (!state.skills.length) {
            state.skills = deriveSkillsFromCategories(state.categories);
          }
          index++; renderStep();
        };
      } 
      else if (step === 2) { 
        body.innerHTML = `
          <section class="wiz-card">
            <h3 class="wiz-h3">技能分析 Dashboard</h3>
            <p class="note">此處將顯示與您所選技能相關的數據分析圖表。</p>
            <div style="height:300px; background:#f3f4f6; border-radius:10px; display:grid; place-items:center; color:#9ca3af; font-weight:800; font-size:1.1rem; border:2px dashed #e5e7eb;">
              (Dashboard 內容之後會補上)
            </div>
          </section>`;
        
        btnNext.onclick = ()=>{
          index++; 
          renderStep();
        };
      }
      else if (step === 3) { 
        if (!state.skills.length && state.categories.length) {
          state.skills = deriveSkillsFromCategories(state.categories);
        }
        const base = state.skills;
        const selected = new Set(base);
        body.innerHTML = `
          <section class="wiz-card">
            <div class="wiz-row-between">
              <h3 class="wiz-h3">調整要強化的技能</h3>
              <div class="wiz-mini-actions">
                <button type="button" class="btn" id="btnClear">全部取消</button>
                <button type="button" class="btn" id="btnAll">全部選取</button>
              </div>
            </div>
            <div class="chip-wrap" id="skillWrap">
              ${base.map(txt => chipHTML(txt, selected.has(txt))).join('')}
            </div>
          </section>`;

        const wrap  = body.querySelector('#skillWrap');
        const chips = [...wrap.querySelectorAll('label.chip')];
        chips.forEach(lab=>{
          const input = lab.querySelector('input');
          const sync = ()=> lab.classList.toggle('active', input.checked);
          sync();
          input.addEventListener('change', sync);
          lab.addEventListener('click', (e)=>{ if(e.target!==input){ e.preventDefault(); input.checked=!input.checked; sync(); }});
        });
        body.querySelector('#btnClear').onclick = ()=> chips.forEach(l=>{const i=l.querySelector('input'); i.checked=false; l.classList.remove('active');});
        body.querySelector('#btnAll').onclick   = ()=> chips.forEach(l=>{const i=l.querySelector('input'); i.checked=true;  l.classList.add('active');});

        btnNext.onclick = ()=>{
          state.skills = [...wrap.querySelectorAll('label.chip input:checked')].map(i=>i.closest('label.chip').dataset.val).slice(0,30);
          index++; renderStep();
        };
      }
      else if (step === 4) {
        body.innerHTML = `
          <section class="wiz-card">
            <h3 class="wiz-h3">設定你的學習條件</h3>
            <div class="input-grid">
              <label>每週時數（hr）
                <input id="wizHours" type="number" min="0" value="${Number(state.hours||0)}">
              </label>
              <label>預算（NTD）
                <input id="wizBudget" type="number" min="0" value="${Number(state.budget||0)}">
              </label>
              <label>總時長（月）
                <input id="wizMonths" type="number" min="0" value="${Number(state.durationMonths||0)}">
              </label>
              <label>總時長（週）
                <input id="wizWeeks" type="number" min="0" value="${Number(state.durationWeeks||0)}">
              </label>
            </div>
            <p class="note" id="wizHint"></p>
          </section>`;
        
        const hoursEl = body.querySelector('#wizHours');
        const budgetEl= body.querySelector('#wizBudget');
        const mEl     = body.querySelector('#wizMonths');
        const wEl     = body.querySelector('#wizWeeks');
        const hint    = body.querySelector('#wizHint');

        function updateHint(){
          let m=Math.max(0,Number(mEl.value||0));
          let w=Math.max(0,Number(wEl.value||0));
          if (w>=4){ m+=Math.floor(w/4); w=w%4; mEl.value=m; wEl.value=w; }
          const totalWeeks=m*4+w;
          const totalHours=(Number(hoursEl.value||0))*totalWeeks;
          hint.textContent=`共 ${totalWeeks} 週，估計可用總時數：${totalHours} 小時`;
        }
        [hoursEl,budgetEl,mEl,wEl].forEach(i=>i.addEventListener('input',updateHint));
        updateHint();
        
        btnFinish.onclick = () => {
          state.hours = Number(hoursEl.value || 0);
          state.budget = Number(budgetEl.value || 0);
          state.durationMonths = Number(mEl.value || 0);
          state.durationWeeks = Number(wEl.value || 0);
          
          const params = new URLSearchParams({
              categories: state.categories.join(','),
              skills: state.skills.join(','),
              hours: state.hours,
              budget: state.budget,
              d_months: state.durationMonths,
              d_weeks: state.durationWeeks
          });

          window.location.href = `./results.html?${params.toString()}`;
        };
      }
    }

    btnCancel.onclick = () => root.remove();
    btnClose.onclick = () => root.remove();

    doc.body.appendChild(root);
    renderStep();
  }

  win.SchedulerWizard = {
    open(initial) { buildWizard(initial || {}); }
  };
})(window, document);