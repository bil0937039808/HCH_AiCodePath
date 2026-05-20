// frontend/web/chatbot.js (最終修正版)
import { getSessionID, getSocket } from './mode.js';

document.addEventListener('DOMContentLoaded', async () => {
    const messagesContainer = document.getElementById('chat');
    const messageInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const quickChipsContainer = document.getElementById('quickchips');

    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'w-fit max-w-[85%] self-start rounded-lg rounded-bl-none border border-gray-200 bg-white p-3 text-sm text-gray-700';
    typingIndicator.innerHTML = `<span>...</span>`;

    let local_session_id = getSessionID();
    let socket_local = null;
    let userInfo = null; // <--- 新增一個變數來儲存使用者資訊

    // --- START: 新增一個函式來獲取並儲存使用者狀態 ---
    async function fetchUserStatus() {
        try {
            const response = await fetch('/api/status');
            if (response.ok) {
                const data = await response.json();
                if (data.logged_in) {
                    userInfo = data; // 如果已登入，儲存整個使用者物件
                    console.log('使用者已登入:', userInfo);
                }
            }
        } catch (error) {
            console.error('獲取使用者狀態失敗:', error);
        }
    }
    await fetchUserStatus(); // 在頁面載入時立刻執行
    // --- END: 新增函式 ---

    // --- START: 新增載入歷史紀錄的函式 ---
    function loadChatHistory() {
        const chatToLoadJSON = sessionStorage.getItem('chat_to_load');
        if (chatToLoadJSON) {
            try {
                // sessionStorage 儲存的是 JSON 字串，需要再解析一次
                const historyMessages = JSON.parse(chatToLoadJSON);

                if (Array.isArray(historyMessages)) {
                    // 清空預設的 "嗨！請描述..." 訊息
                    messagesContainer.innerHTML = '';
                    // 載入歷史訊息
                    historyMessages.forEach(msg => {
                        addMsg(msg.content, msg.role);
                    });
                    console.log("成功載入歷史對話紀錄。");
                }
            } catch (e) {
                console.error("解析或載入歷史對話失敗:", e);
            } finally {
                // 無論成功或失敗，都清除此項目，避免重複載入
                sessionStorage.removeItem('chat_to_load');
            }
        }
    }
    // --- END: 新增載入歷史紀錄的函式 ---

    // 頁面載入時，立刻檢查是否有歷史紀錄要載入
    loadChatHistory();

    try {
        socket_local = await getSocket(local_session_id);
        console.log("chatbot.js: WebSocket 連線已成功取得。");

        socket_local.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("收到後端 WebSocket 推送:", data);

            if (typingIndicator.parentNode) {
                messagesContainer.removeChild(typingIndicator);
            }

            if (data.msg_name === "jobs_filters_answer") {
                addMsg(data.answer, 'bot');
            } else if (data.msg_name === "process_job_search_result") {
                const successMsg = `<button class="generate-jobs-btn"><i class="fa-solid fa-gift"></i> 點此查看為您產生的職缺</button>`;
                addMsg(successMsg, 'bot', true);

                if (data.data) {
                    localStorage.setItem('jobList', JSON.stringify(data.data));
                }
            }
        };
    } catch (error) {
        console.error("chatbot.js: WebSocket 連線初始化失敗。", error);
        addMsg('聊天室連線失敗，請重新整理頁面。', 'bot');
    }

    // --- 3. 核心功能函式 ---

    /**
     * 新增訊息到對話框
     * @param {string} content - 訊息內容 (可以是純文字或 HTML)
     * @param {string} who - 'user' 或 'bot'
     * @param {boolean} isHTML - 內容是否為 HTML
     */
    function addMsg(content, who = 'bot', isHTML = false) {
        const div = document.createElement('div');
        div.className = `w-fit max-w-[85%] rounded-lg p-3 text-sm text-gray-700 ${who === 'user' ? 'self-end rounded-br-none bg-teal-100' : 'self-start rounded-bl-none border border-gray-200 bg-white'}`;

        if (isHTML) {
            div.innerHTML = content;
        } else {
            div.style.whiteSpace = 'pre-line';
            div.textContent = content;
        }

        messagesContainer.appendChild(div);
        // 自動捲動到最新訊息
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    /**
     * 處理使用者發送訊息的流程
     * @param {string} text - 使用者輸入的文字
     */
    const sendMessage = (text) => {
        const messageText = text.trim();
        if (messageText === '') return;

        addMsg(messageText, 'user');
        messageInput.value = '';

        triggerBotResponse(messageText);
    };

    /**
     * 觸發後端機器人回覆
     * @param {string} userMessage - 使用者的訊息
     */
    const triggerBotResponse = (userMessage) => {
        if (!socket_local || socket_local.readyState !== WebSocket.OPEN) {
            console.error("WebSocket 尚未連線，無法發送訊息。");
            addMsg('連線中斷，請重新整理頁面再試。', 'bot');
            return;
        }

        messagesContainer.appendChild(typingIndicator);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // 建立要發送的資料物件
        const messagePayload = {
            send_name: "chat",
            message: userMessage,
            session_id: local_session_id
        };

        // 如果使用者已登入，就附加上 member_id
        if (userInfo && userInfo.member_id) {
            messagePayload.member_id = userInfo.member_id;
        }

        // 透過 WebSocket 發送訊息
        socket_local.send(JSON.stringify(messagePayload));
    };

    // --- 4. 事件監聽器 ---

    // 點擊發送按鈕
    sendBtn.addEventListener('click', () => sendMessage(messageInput.value));

    // 在輸入框按 Enter
    messageInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) { // 按 Enter 發送, Shift+Enter 換行
            event.preventDefault();
            sendMessage(messageInput.value);
        }
    });

    // 點擊快速回覆標籤
    if (quickChipsContainer) {
        quickChipsContainer.addEventListener('click', (event) => {
            if (event.target.matches('[data-insert]')) {
                const textToInsert = event.target.dataset.insert;
                messageInput.value = (messageInput.value + ' ' + textToInsert).trim();
                messageInput.focus();
            }
        });
    }

    // 點擊「產生職缺」按鈕 (使用事件委派)
    messagesContainer.addEventListener('click', function (e) {
        const targetButton = e.target.closest('.generate-jobs-btn');
        if (targetButton) {
            window.location.href = `./jobs.html`;
        }
    });
});