/**
 * 排課結果頁面 JavaScript
 * 整合後端 WebSocket 資料並處理頁面互動
 */
import { getSessionID, getSocket } from './mode.js';
class CourseResultsManager {
  constructor() {
    this.currentPageIndex = 0;
    this.userState = {};
    this.coursesData = [];
    this.socket_local = null;
    this.local_session_id = null;
    this.isDataLoaded = false;

    // DOM 元素
    this.navEl = document.getElementById('results-nav');
    this.bodyEl = document.getElementById('result-body');
    this.prevBtn = document.getElementById('result-prev-btn');
    this.nextBtn = document.getElementById('result-next-btn');
    this.finishBtn = document.getElementById('result-finish-btn');
    this.loadingEl = document.getElementById('loading-spinner');
    this.errorEl = document.getElementById('error-message');
    this.retryBtn = document.getElementById('retry-btn');

    this.init();
  }

  init() {
    this.local_session_id = getSessionID();
    this.socket_local = getSocket(this.local_session_id);
    console.log("CourseResultsManager")
    this.parseURLParams();
    this.setupEventListeners();
    this.setupWebSocket();
    this.showLoading();
  }

  /**
   * 解析 URL 參數獲取用戶狀態
   */
  parseURLParams() {
    const params = new URLSearchParams(window.location.search);
    this.userState = {
      categories: params.get('categories') ? params.get('categories').split(',') : [],
      skills: params.get('skills') ? params.get('skills').split(',') : [],
      hours: Number(params.get('hours') || 0),
      budget: Number(params.get('budget') || 0),
      durationMonths: Number(params.get('d_months') || 0),
      durationWeeks: Number(params.get('d_weeks') || 0)
    };
  }

  /**
   * 設置事件監聽器
   */
  setupEventListeners() {
    // 導航點擊
    this.navEl.addEventListener('click', (e) => {
      const navItem = e.target.closest('.results-nav-item');
      if (navItem && navItem.dataset.index) {
        this.navigate(parseInt(navItem.dataset.index, 10));
      }
    });

    // 按鈕點擊
    this.prevBtn.addEventListener('click', () => this.navigate(this.currentPageIndex - 1));
    this.nextBtn.addEventListener('click', () => this.navigate(this.currentPageIndex + 1));
    this.finishBtn.addEventListener('click', () => { window.location.href = './index.html'; });
    this.retryBtn.addEventListener('click', () => this.retryConnection());
  }

  /**
   * 設置 WebSocket 連接
   */
  setupWebSocket() {
    try {
      // 優先檢查 sessionStorage 中是否有暫存的課程資料
      const cachedData = sessionStorage.getItem('courseRecommendations');
      if (cachedData) {
        try {
          const data = JSON.parse(cachedData);
          console.log('從 sessionStorage 載入課程資料');
          sessionStorage.removeItem('courseRecommendations'); // 清除暫存
          this.handleBackendData(data);
          return;
        } catch (error) {
          console.error('解析暫存資料失敗:', error);
          sessionStorage.removeItem('courseRecommendations');
        }
      }

      this.showError();

      // 如果沒有暫存資料，設置 WebSocket 監聽
      // if (typeof this.socket_local !== 'undefined') {
      //   this.socket_local.onmessage = (event) => {
      //     try {
      //       console.log("後端資料:", event.data)
      //       const data = JSON.parse(event.data);
      //       if (data.msg_name == "courses_recommend") {
      //         // --- FIX: 直接傳遞 recommendations 陣列 ---
      //         // 檢查 data.data 是否存在且為物件，再取出 recommendations 陣列
      //         if (data.data && Array.isArray(data.data.recommendations)) {
      //           this.handleBackendData(data.data.recommendations);
      //         } else {
      //           console.error('後端回傳的課程資料結構不符預期:', data);
      //           this.showError();
      //         }
      //       }
      //     } catch (error) {
      //       console.error('解析後端資料失敗:', error);
      //       this.showError();
      //     }
      //   };

      //   this.socket_local.onerror = () => {
      //     this.showError();
      //   };
      // } else {
      //   // 開發階段可以使用模擬資料
      //   setTimeout(() => {
      //     //this.handleBackendData(this.getMockData());
      //   }, 60000);
      // }
    } catch (error) {
      console.error('讀取課程資料或 WebSocket 連接失敗:', error);
      this.showError();
    }
  }

  /**
   * 處理後端資料
   */
  handleBackendData(data) {
    // 即使是空陣列也視為成功，但會在頁面上顯示無結果
    if (Array.isArray(data)) {
      this.coursesData = data.map(course => this.transformCourseData(course));
      this.isDataLoaded = true;
      this.hideLoading();
      this.renderPage(); // renderPage 內部會處理 coursesData 為空的情況
    } else {
      this.showError();
    }
  }

  /**
   * 轉換後端課程資料格式以符合前端需求
   */
  transformCourseData(backendCourse) {
    return {
      rank: backendCourse.rank,
      title: backendCourse.course_title,
      url: backendCourse.course_url,
      reason: backendCourse.reason,
      level: backendCourse.level,
      skills: backendCourse.skills,
      hours: backendCourse.Course_duration,
      webReview: backendCourse.web_review,
      prepNotes: backendCourse.prep_notes,
      // 為了保持向後兼容，添加一些原有格式的欄位
      provider: this.extractProvider(backendCourse.course_url),
      skill: backendCourse.skills.split(',')[0].trim(), // 取第一個技能作為主要技能
      rating: this.levelToRating(backendCourse.level),
      price: 0 // 暫時設為免費，可根據需求調整
    };
  }

  /**
   * 從 URL 提取供應商名稱
   */
  extractProvider(url) {
    if (url.includes('coursera.org')) return 'Coursera';
    if (url.includes('udemy.com')) return 'Udemy';
    if (url.includes('hahow.in')) return 'Hahow';
    return '其他平台';
  }

  /**
   * 將等級轉換為評級
   */
  levelToRating(level) {
    const levelMap = {
      'Beginner': 'A',
      'Intermediate': 'B',
      'Advanced': 'S'
    };
    return levelMap[level] || 'B';
  }

  /**
   * 獲取模擬資料（開發用）
   */
  getMockData() {
    return [
      {
        rank: 1,
        course_title: 'Supervised Machine Learning: Regression and Classification',
        course_url: 'https://www.coursera.org/learn/supervised-machine-learning-regression-classification',
        reason: '此課程由 AI 領域的權威吳恩達（Andrew Ng）教授，是全球公認最適合機器學習入門的課程。',
        level: 'Beginner',
        skills: '機器學習, 演算法設計, 軟體程式設計',
        Course_duration: 33,
        web_review: '全球學習者一致推崇為「機器學習入門聖經」。',
        prep_notes: '1. 熟悉基礎 Python 語法\n2. 複習高中程度的數學概念'
      },
      {
        rank: 2,
        course_title: 'Databases and SQL for Data Science with Python',
        course_url: 'https://www.coursera.org/learn/sql-data-science',
        reason: 'AI 與機器學習的基礎是資料，因此學習如何存取和管理資料庫至關重要。',
        level: 'Beginner',
        skills: '資料庫軟體應用',
        Course_duration: 15,
        web_review: '作為 IBM 數據科學專業證書的一部分，此課程因其清晰的結構和豐富的線上實作環境而備受好評。',
        prep_notes: '1. 了解資料庫的基本概念\n2. 無需預先學習程式語言'
      }
    ];
  }

  /**
   * 顯示載入中
   */
  showLoading() {
    this.loadingEl.style.display = 'block';
    this.errorEl.style.display = 'none';
  }

  /**
   * 隱藏載入中
   */
  hideLoading() {
    this.loadingEl.style.display = 'none';
  }

  /**
   * 顯示錯誤訊息
   */
  showError() {
    this.loadingEl.style.display = 'none';
    this.errorEl.style.display = 'block';
  }

  /**
   * 重試連接
   */
  retryConnection() {
    this.showLoading();
    this.setupWebSocket();
  }

  /**
   * 頁面定義
   */
  get RESULT_PAGES() {
    return [
      {
        title: '推薦課程',
        icon: 'fa-list-check',
        render: () => this.renderCoursesPage()
      },
      // {
      //   title: '課程詳情',
      //   icon: 'fa-info-circle',
      //   render: () => this.renderCourseDetailsPage()
      // },
      {
        title: '學習準備',
        icon: 'fa-clipboard-list',
        render: () => this.renderPrepNotesPage()
      },
      {
        title: '匯入日曆',
        icon: 'fa-calendar-plus',
        render: () => this.renderCalendarPage()
      },
      {
        title: '進度追蹤',
        icon: 'fa-chart-line',
        render: () => this.renderTrackingPage()
      }
    ];
  }

  /**
   * 渲染推薦課程頁面
   */
  renderCoursesPage() {
    const totalWeeks = this.userState.durationMonths * 4 + this.userState.durationWeeks;
    const totalHours = this.userState.hours * totalWeeks;
/*
        <div class="mb-4 flex flex-wrap gap-2">
          ${(this.userState.categories || []).map(c => `<span class="rounded-full bg-teal-100 px-3 py-1 text-xs font-medium text-teal-700">${c}</span>`).join(' ')}
          <span class="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600">${(this.userState.skills || []).length} 項技能</span>
          <span class="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600">${this.userState.hours || 0}h/週</span>
          <span class="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600">週數：${totalWeeks}</span>
        </div> 


        <div class="mt-6 p-4 bg-teal-50 rounded-lg">
        <p class="text-sm font-medium text-teal-800">
          <i class="fa-solid fa-lightbulb mr-2"></i>
          估計總可用時數：<span class="font-bold">${totalHours}</span> 小時
        </p>
      </div>
      <div class="mb-6" style="display: flex; align-items: center;">
        
      </div>
*/
    return `
      <h2 class="text-xl font-bold text-gray-800" style="display: flex; justify-content: center; align-items: center;">為您推薦的課程</h2>
      <div class="space-y-4">
        ${this.coursesData.map(course => `
          <div class="flex items-start gap-4 rounded-lg border border-gray-100 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
            <div class="flex-shrink-0">
              <div class="flex items-center justify-center w-8 h-8 bg-teal-100 text-teal-600 rounded-full font-bold text-sm">
                ${course.rank}
              </div>
            </div>
            <div class="flex-1">
              <div class="flex items-start justify-between mb-2">
                <h3 class="font-bold text-gray-800 text-lg pr-4">${course.title}</h3>
                ${this.badgeByRating(course.rating)}
              </div>
              <p class="text-sm text-gray-600 mb-3 leading-relaxed">${course.reason}</p>
              <div class="flex flex-wrap items-center gap-4 text-xs text-gray-500 mb-3">
                <span><i class="fa-solid fa-graduation-cap mr-1"></i>${course.provider}</span>
                <span><i class="fa-solid fa-clock mr-1"></i>${course.hours} 小時</span>
                <span><i class="fa-solid fa-signal mr-1"></i>${course.level}</span>
                <span><i class="fa-solid fa-tags mr-1"></i>${course.skills}</span>
              </div>
              <a href="${course.url}" target="_blank" rel="noopener" 
                 class="inline-flex items-center gap-1 rounded-md bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700">
                <i class="fa-solid fa-external-link text-xs"></i>
                查看課程
              </a>
            </div>
          </div>
        `).join('')}
      </div>
      
      
    `;
  }

  /**
   * 渲染課程詳情頁面
   */
  renderCourseDetailsPage() {
    return `
      <div class="mb-6">
        <h2 class="text-xl font-bold text-gray-800 mb-4">課程詳細評價</h2>
      </div>
      
      <div class="space-y-6">
        ${this.coursesData.map(course => `
          <div class="rounded-lg border border-gray-100 bg-white p-6">
            <h3 class="font-bold text-lg text-gray-800 mb-3">${course.title}</h3>
            <div class="bg-blue-50 p-4 rounded-lg">
              <h4 class="font-medium text-blue-800 mb-2">
                <i class="fa-solid fa-star mr-2"></i>網路評價
              </h4>
              <p class="text-sm text-blue-700 leading-relaxed">${course.webReview}</p>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  /**
   * 渲染學習準備頁面
   * 
   * <div class="mb-6">
        <h2 class="text-xl font-bold text-gray-800 mb-4">學習前準備建議</h2>
      </div>
   */
  renderPrepNotesPage() {
    return `
      <h2 class="text-xl font-bold text-gray-800" style="display: flex; justify-content: center; align-items: center;">學習前準備建議</h2>
      
      
      <div class="space-y-6">
        ${this.coursesData.map(course => `
          <div class="rounded-lg border border-gray-100 bg-white p-6">
            <h3 class="font-bold text-lg text-gray-800 mb-3">${course.title}</h3>
            <div class="bg-green-50 p-4 rounded-lg">
              <h4 class="font-medium text-green-800 mb-3">
                <i class="fa-solid fa-clipboard-check mr-2"></i>準備事項
              </h4>
              <div class="text-sm text-green-700 space-y-1">
                ${course.prepNotes.split('\n').map(note =>
      note.trim() ? `<p class="leading-relaxed">${note}</p>` : ''
    ).join('')}
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  /**
   * 渲染日曆匯入頁面
   */
  renderCalendarPage() {
    return `
      <div class="text-center py-12">
        <i class="fa-brands fa-google text-6xl text-gray-300 mb-6"></i>
        <h3 class="text-xl font-bold text-gray-800 mb-4">匯入 Google 日曆</h3>
        <p class="text-gray-600 mb-8 max-w-md mx-auto leading-relaxed">
          將推薦課程與學習時程匯入您的 Google 日曆，讓學習計畫一目了然。
        </p>
        <button class="rounded-lg bg-gray-400 px-6 py-3 text-sm font-medium text-white cursor-not-allowed" disabled>
          <i class="fa-solid fa-calendar-plus mr-2"></i>
          立即匯入 (功能開發中)
        </button>
      </div>
    `;
  }

  /**
   * 渲染追蹤頁面
   */
  renderTrackingPage() {
    return `
      <div class="text-center py-12 text-gray-500">
        <i class="fa-solid fa-chart-line text-6xl text-gray-300 mb-6"></i>
        <h3 class="text-xl font-bold text-gray-800 mb-4">學習進度追蹤</h3>
        <p class="text-gray-600 max-w-md mx-auto leading-relaxed">
          您可以在此追蹤已完成的課程時數與學習成效。(功能開發中)
        </p>
      </div>
    `;
  }

  /**
   * 根據評級生成徽章
   */
  badgeByRating(rating) {
    const classMap = {
      'S': 'bg-purple-100 text-purple-800',
      'A': 'bg-green-100 text-green-800',
      'B': 'bg-blue-100 text-blue-800',
      'C': 'bg-yellow-100 text-yellow-800',
      'D': 'bg-red-100 text-red-800'
    };
    const classes = classMap[rating] || 'bg-gray-100 text-gray-800';
    return `<span class="inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${classes}">${rating}</span>`;
  }

  /**
   * 渲染當前頁面
   */
  renderPage() {
    if (!this.isDataLoaded) return;

    const pages = this.RESULT_PAGES;

    // 渲染導航
    this.navEl.innerHTML = pages
      .map((p, i) => `
        <button class="results-nav-item ${i === this.currentPageIndex ? 'active' : ''}" data-index="${i}">
          <i class="fa-solid ${p.icon} w-5 text-center"></i>
          <span>${p.title}</span>
        </button>
      `).join('');

    // 渲染頁面內容
    const page = pages[this.currentPageIndex];
    this.bodyEl.innerHTML = `
      <div class="rounded-lg border border-gray-200 bg-white shadow-sm">
        ${page.render()}
      </div>
    `;

    // 更新按鈕狀態
    this.prevBtn.disabled = this.currentPageIndex === 0;
    this.nextBtn.style.display = (this.currentPageIndex === pages.length - 1) ? 'none' : 'inline-flex';
    this.finishBtn.style.display = (this.currentPageIndex === pages.length - 1) ? 'inline-flex' : 'none';
  }

  /**
   * 導航到指定頁面
   */
  navigate(index) {
    const pages = this.RESULT_PAGES;
    if (index >= 0 && index < pages.length && this.isDataLoaded) {
      this.currentPageIndex = index;
      this.renderPage();
    }
  }
}

// 頁面載入完成後初始化
document.addEventListener('DOMContentLoaded', () => {
  new CourseResultsManager();
});