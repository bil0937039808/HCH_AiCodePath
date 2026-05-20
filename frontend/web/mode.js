// frontend/web/mode.js

// 將 socket 變數移到最外層，使其成為一個跨模組共享的單例
let socket = null;
let connectingPromise = null;
export function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}
export function getSessionID() {
    // let session_id = localStorage.getItem("session_id");
    // if (!session_id) {
    //     session_id = crypto.randomUUID();
    //     localStorage.setItem("session_id", session_id);
    // }
    // return session_id;
    let session_id = localStorage.getItem("session_id");
    if (!session_id) {
        if (typeof crypto.randomUUID === 'function') {
            session_id = crypto.randomUUID();
        } else {
            session_id = uuidv4(); // 使用備用函式
        }
        localStorage.setItem("session_id", session_id);
    }
    return session_id;
}

// getSocket 函數現在會返回一個 Promise，確保呼叫者能拿到已連線的 socket
export function getSocket(set_id) {
    // 如果已有可用連線，直接返回
    if (socket && socket.readyState === WebSocket.OPEN) {
        console.log("WebSocket: 使用現有連線。");
        return Promise.resolve(socket);
    }

    // 如果正在連線中，返回同一個正在處理的 Promise，避免重複建立
    if (connectingPromise) {
        console.log("WebSocket: 正在連線中，等待連線完成...");
        return connectingPromise;
    }

    // 建立新的連線 Promise
    connectingPromise = new Promise((resolve, reject) => {
        console.log("WebSocket: 建立新連線...");
        // 使用相對路徑，讓 Nginx 處理轉發
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/${set_id}`;
        //fetch("/api/some-endpoint")
        //const socket = new WebSocket("ws://" + window.location.host + "/ws/endpoint")

        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log("WebSocket: 連線成功。");
            connectingPromise = null; // 連線成功，清除 Promise 鎖
            resolve(socket);
        };

        socket.onclose = () => {
            console.log("WebSocket: 連線已斷開。");
            socket = null; // 清理舊的 socket 實例
            connectingPromise = null;
        };

        socket.onerror = (error) => {
            console.error("WebSocket 錯誤:", error);
            socket = null;
            connectingPromise = null;
            reject(error);
        };
    });
    // return socket;
    return connectingPromise;
}

// 為了讓其他 JS 檔案能非同步地取得 socket
// 例如在 chatbot.js 中可以這樣使用：
//
// import { getSessionID, getSocket } from './mode.js';
//
// async function initChat() {
//     const local_session_id = getSessionID();
//     try {
//         const socket_local = await getSocket(local_session_id);
//         // 在這裡設定 onmessage 等事件處理器
//     } catch (error) {
//         console.error("無法建立 WebSocket 連線:", error);
//     }
// }