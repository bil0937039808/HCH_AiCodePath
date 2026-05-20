// AIPE01_G4_AiCodePath/frontend/web/main.js

import { getSessionID, getSocket } from './mode.js';

// 使用 async IIFE (立即執行的非同步函式) 來包裹整個模組
(async function (win, doc) {
    // --- DOM 元素宣告 (維持不變) ---
    const gridEl = doc.getElementById('jobCardsContainer');
    const summaryEl = doc.getElementById('resultsSummary');
    const scheduleBtn = doc.getElementById('schedule-result-btn');
    const pagerEl = doc.getElementById('pagination-container');

    // --- 常數與全域變數 (維持不變) ---
    const PAGE_SIZE = 9;
    const EXCLUDED_SKILLS = new Set(['Excel', 'Word', '中文打字20~50', '不拘', 'N/A', '']);

    let jobList = [];
    function loadJobsFromStorage() {
        try {
            const storedListJSON = localStorage.getItem('jobList');
            if (storedListJSON) {
                const parsedList = JSON.parse(storedListJSON);
                if (Array.isArray(parsedList)) {
                    console.log(`成功從 localStorage 載入 ${parsedList.length} 筆職缺資料。`);
                    return parsedList;
                }
            }
        } catch (error) {
            console.error('從 localStorage 解析 jobList 失敗:', error);
        }
        console.log('localStorage 中無有效的職缺資料。');
        return [];
    }
    jobList = loadJobsFromStorage();

    let local_session_id = null;
    let socket_local = null;

    // --- WebSocket 初始化與 onmessage 事件處理 ---
    try {
        local_session_id = getSessionID();
        socket_local = await getSocket(local_session_id);
        console.log("main.js: WebSocket 連線已成功建立。");

        // --- START: 修改 onmessage 處理邏輯 ---
        socket_local.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("main.js 收到後端推送:", data);

            if (data.msg_name === "courses_recommend") {
                console.log("已接收到課程推薦資料:", data.data);

                if (data.data && Array.isArray(data.data.recommendations)) {
                    // 1. 將推薦資料陣列存入 sessionStorage
                    sessionStorage.setItem('courseRecommendations', JSON.stringify(data.data.recommendations));

                    // 2. 準備 URL 參數
                    const skills = collectSelectedSkills();
                    const urlParams = new URLSearchParams();
                    urlParams.set('categories', '');
                    urlParams.set('skills', skills.join(','));
                    urlParams.set('hours', '5');
                    urlParams.set('budget', '0');
                    urlParams.set('d_months', '3');
                    urlParams.set('d_weeks', '0');
                    urlParams.set('source', 'job_skills');

                    // 3. 儲存完畢後立刻跳轉
                    window.location.assign(`./results.html?${urlParams.toString()}`);
                } else {
                    console.error("收到的課程推薦資料格式不正確", data);
                    alert('處理請求失敗，請稍後再試');
                    if (scheduleBtn) {
                        scheduleBtn.disabled = false;
                        scheduleBtn.innerHTML = `<span>排課結果</span>`;
                    }
                }
            }
        };
        // --- END: 修改 onmessage 處理邏輯 ---

    } catch (error) {
        console.error("main.js: WebSocket 連線初始化失敗。", error);
        if (scheduleBtn) {
            scheduleBtn.disabled = true;
            scheduleBtn.title = "後端連線失敗，功能暫時無法使用。";
        }
    }

    // --- 從 localStorage 載入資料 (維持不變) ---
    try {
        const storedList = localStorage.getItem('jobList');
        if (storedList) {
            jobList = JSON.parse(storedList);
        }
    } catch (error) {
        console.error('從 localStorage 解析 jobList 失敗:', error);
    }

    // =================================================================
    // 底下的狀態管理、輔助函式與渲染函式完全不需要變動
    // ... (state, parseSkills, uniq, paginate, fmtText, renderSummary, renderPager, jobCardHTML, bindCardEvents, renderGrid) ...
    // =================================================================

    // --- 狀態管理物件 ---
    const state = {
        list: jobList,
        page: 1,
        selected: new Set(),
    };

    // --- 輔助函式 ---
    function parseSkills(str) {
        if (!str) return [];
        return String(str).split(',').map(s => s.trim()).filter(s => s && !EXCLUDED_SKILLS.has(s));
    }

    function uniq(arr) {
        return Array.from(new Set(arr));
    }

    function paginate(arr, page = 1, size = PAGE_SIZE) {
        const start = (page - 1) * size;
        return arr.slice(start, start + size);
    }

    function fmtText(v, fallback = '未提供') {
        return (v === undefined || v === null || String(v).trim() === '') ? fallback : String(v);
    }

    // --- 渲染相關函式 ---
    function renderSummary() {
        const total = state.list.length;
        const selCount = state.selected.size;
        summaryEl.textContent = `共找到 ${total} 筆職缺${selCount ? `（已選 ${selCount} 筆）` : ''}`;
    }

    function renderPager() {
        const total = state.list.length;
        const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
        if (pages <= 1) {
            pagerEl.innerHTML = '';
            return;
        }
        let html = '<ol class="flex justify-center gap-1 text-xs font-medium list-none">';
        const isFirstPage = state.page === 1;
        html += `<li><button data-page="${state.page - 1}" class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-900 rtl:rotate-180" ${isFirstPage ? 'disabled style="opacity:0.5; cursor:not-allowed;"' : ''}><span class="sr-only">上一頁</span><svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" /></svg></button></li>`;
        for (let i = 1; i <= pages; i++) {
            const isActive = i === state.page;
            html += `<li><button data-page="${i}" class="block h-8 w-8 rounded-lg border text-center leading-8 ${isActive ? 'border-teal-600 bg-teal-600 text-white' : 'border-gray-200 bg-white text-gray-900'}">${i}</button></li>`;
        }
        const isLastPage = state.page === pages;
        html += `<li><button data-page="${state.page + 1}" class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-900 rtl:rotate-180" ${isLastPage ? 'disabled style="opacity:0.5; cursor:not-allowed;"' : ''}><span class="sr-only">下一頁</span><svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg></button></li>`;
        html += '</ol>';
        pagerEl.innerHTML = html;
        pagerEl.querySelectorAll('button[data-page]').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.disabled) return;
                const p = Number(btn.dataset.page);
                if (p > 0 && p <= pages && p !== state.page) {
                    state.page = p;
                    render();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            });
        });
    }

    function jobCardHTML(job, id, isSelected) {
        const title = fmtText(job.jobTitle);
        const company = fmtText(job.companyName, '');
        const salary = fmtText(job.salary);
        const loc = fmtText(job.location);
        const link = job.jobLink ? String(job.jobLink) : '';
        const skills = parseSkills(job.skills).slice(0, 4);
        return `
        <article class="group relative block h-full bg-white border ${isSelected ? 'border-teal-600 shadow-teal-500/10' : 'border-gray-200'} shadow-sm rounded-lg transition hover:shadow-lg">
            <label class="absolute end-4 top-4 z-10 rounded-full bg-white p-1.5 text-gray-900 transition hover:text-gray-900/75">
            <input type="checkbox" class="job-select h-4 w-4 rounded-md border-gray-300 text-teal-600 focus:ring-teal-500" data-id="${id}" ${isSelected ? 'checked' : ''} />
            </label>
            
            <div class="p-6">
            ${link && link !== `<h3 class="mt-1 text-lg font-bold text-gray-900">${title}</h3>` ? `
                <a href="${link}" target="_blank" rel="noopener" class="mt-1 text-lg font-bold text-gray-900" >${title}</a>
                ` : ''}
            <p class="text-sm font-medium text-gray-500">${company}</p>
            <div class="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm text-gray-600">
                <span><i class="fa-solid fa-location-dot mr-1.5"></i>${loc}</span>
                <span><i class="fa-solid fa-sack-dollar mr-1.5"></i>${salary}</span>
            </div>

            ${skills.length > 0 ? `
                <div class="mt-4 flex flex-wrap gap-1">
                ${skills.map(s => `
                    <span class="whitespace-nowrap rounded-full bg-teal-100 px-2.5 py-0.5 text-xs text-teal-700">
                    ${s}
                    </span>
                `).join('')}
                </div>
            ` : ''}
            </div>
        </article>`;//${title}<div class="flex justify-center items-end">
    }

    function bindCardEvents() {
        gridEl.querySelectorAll('.job-select').forEach(cb => {
            cb.addEventListener('change', (e) => {
                e.stopPropagation();
                const id = Number(cb.dataset.id);
                if (cb.checked) {
                    state.selected.add(id);
                } else {
                    state.selected.delete(id);
                }
                renderGrid();
                updateScheduleBtnState();
                renderSummary();
            });
        });
    }

    function renderGrid() {
        const pageList = paginate(state.list, state.page, PAGE_SIZE);
        if (!pageList.length) {
            gridEl.innerHTML = `<p class="text-gray-500 md:col-span-2 lg:col-span-3">目前沒有可顯示的職缺。</p>`;
            return;
        }
        gridEl.innerHTML = pageList.map((job, i) => {
            const globalId = (state.page - 1) * PAGE_SIZE + i;
            return jobCardHTML(job, globalId, state.selected.has(globalId));
        }).join('');
        bindCardEvents();
    }

    // --- 事件處理與邏輯函式 (scheduleBtn 邏輯已修改) ---
    function updateScheduleBtnState() {
        const hasSelection = state.selected.size > 0;
        if (scheduleBtn) {
            scheduleBtn.disabled = !hasSelection;
            const buttonText = scheduleBtn.querySelector('span');
            if (buttonText) {
                buttonText.textContent = hasSelection ? `排課結果 (${state.selected.size})` : '排課結果';
            }
        }
    }

    function collectSelectedSkills() {
        const skills = [];
        state.selected.forEach(id => {
            const job = state.list[id];
            if (job && job.skills) {
                parseSkills(job.skills).forEach(s => skills.push(s));
            }
        });
        return uniq(skills);
    }

    // --- START: 修改 scheduleBtn 點擊事件 ---
    if (scheduleBtn) {
        scheduleBtn.addEventListener('click', async () => {
            if (!socket_local /*|| socket_local.readyState !== WebSocket.OPEN*/) {
                console.error("WebSocket 尚未連線或連線已中斷，無法發送技能資料。", socket_local);
                alert("後端服務連線錯誤，請重新整理頁面再試。");
                return;
            }

            const skills = collectSelectedSkills();
            if (!skills.length) {
                alert('請先勾選至少 1 個包含技能的職缺！');
                return;
            }

            // 按鈕點擊後只發送請求，不處理跳轉
            scheduleBtn.disabled = true;
            scheduleBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i>正在產生課程推薦...';

            try {
                socket_local.send(JSON.stringify({
                    send_name: "job_skills",
                    session_id: local_session_id,
                    select_skills: skills
                }));
                console.log("已發送技能資料:", skills);
                // 移除所有跳轉與 URL 處理邏輯
            } catch (error) {
                console.error('處理失敗:', error);
                alert('處理請求失敗，請稍後再試');
                scheduleBtn.disabled = false;
                scheduleBtn.innerHTML = `<span>排課結果</span>`;
            }
        });
    }
    // --- END: 修改 scheduleBtn 點擊事件 ---

    // --- 主渲染函式 (維持不變) ---
    function render() {
        if (!Array.isArray(state.list) || !state.list.length) {
            summaryEl.textContent = '無法載入職缺資料。';
            gridEl.innerHTML = '';
            pagerEl.innerHTML = '';
            if (scheduleBtn) scheduleBtn.disabled = true;
            return;
        }
        renderSummary();
        renderGrid();
        renderPager();
        updateScheduleBtnState();
    }
    // --- 初始執行 (維持不變) ---
    render();

})(window, document);