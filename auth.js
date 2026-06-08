(function() {
  // Hash SHA-256 của mật khẩu mặc định "namoinam2026"
  const CORRECT_HASH = '59b8d155e27284062e66e74c8b34ce50cc3ff7fd1a611be19bab852859ddb7d0';
  
  async function sha256(message) {
    const msgBuffer = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  function checkAuth() {
    const saved = localStorage.getItem('page_auth_hash');
    if (saved === CORRECT_HASH) {
      // Đã xác thực thành công: Gỡ bỏ preload style để hiển thị trang
      const style = document.getElementById('auth-preload-style');
      if (style) style.remove();
      return true;
    }
    return false;
  }

  // Khai báo hàm đăng xuất toàn cục
  window.authLogout = function() {
    localStorage.removeItem('page_auth_hash');
    location.reload();
  };

  // Kiểm tra đăng nhập ngay lập tức khi load file JS
  const isAuthenticated = checkAuth();

  if (!isAuthenticated) {
    // Nếu chưa đăng nhập, đợi DOM sẵn sàng để hiển thị Form đăng nhập
    document.addEventListener('DOMContentLoaded', () => {
      // Kiểm tra lại lần nữa phòng trường hợp tab khác vừa đăng nhập
      if (checkAuth()) return;
      
      // Inject CSS giao diện màn hình khóa
      const css = `
        #auth-container {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: #f3f4f6;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 999999;
          font-family: 'Be Vietnam Pro', sans-serif;
          padding: 20px;
        }
        #auth-card {
          background: #ffffff;
          border: 1px solid #e5e7eb;
          border-radius: 16px;
          padding: 36px 28px;
          width: 100%;
          max-width: 360px;
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.08);
          text-align: center;
          animation: auth-fade-in 0.3s ease-out;
        }
        @keyframes auth-fade-in {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
        #auth-logo { font-size: 44px; margin-bottom: 20px; }
        #auth-title { font-size: 20px; font-weight: 800; margin-bottom: 8px; color: #1f2937; letter-spacing: -0.01em; }
        #auth-sub { font-size: 13px; color: #6b7280; margin-bottom: 28px; line-height: 1.6; }
        #auth-input {
          width: 100%;
          padding: 12px 14px;
          border: 1px solid #d1d5db;
          border-radius: 8px;
          font-size: 14px;
          margin-bottom: 16px;
          box-sizing: border-box;
          text-align: center;
          background: #ffffff;
          color: #1f2937;
          transition: all 0.2s;
        }
        #auth-input:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
        }
        #auth-btn {
          width: 100%;
          padding: 12px;
          background: #3b82f6;
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }
        #auth-btn:hover { background: #2563eb; }
        #auth-error { color: #ef4444; font-size: 12.5px; margin-top: 12px; display: none; font-weight: 600; }
      `;
      const styleTag = document.createElement('style');
      styleTag.textContent = css;
      document.head.appendChild(styleTag);

      // Inject HTML form đăng nhập
      const container = document.createElement('div');
      container.id = 'auth-container';
      container.innerHTML = `
        <div id="auth-card">
          <div id="auth-logo">🔒</div>
          <div id="auth-title">TRANG BẢO MẬT</div>
          <div id="auth-sub">Vui lòng nhập mật khẩu để truy cập công cụ nội bộ namoinam.com</div>
          <form id="auth-form" onsubmit="return false;">
            <input type="password" id="auth-input" placeholder="Mật khẩu truy cập" autofocus autocomplete="current-password">
            <button type="submit" id="auth-btn">Xác nhận</button>
          </form>
          <div id="auth-error">Mật khẩu không chính xác!</div>
        </div>
      `;
      document.body.appendChild(container);

      // Xử lý sự kiện đăng nhập
      const form = document.getElementById('auth-form');
      const input = document.getElementById('auth-input');
      const error = document.getElementById('auth-error');
      
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const pwd = input.value;
        const hash = await sha256(pwd);
        if (hash === CORRECT_HASH) {
          localStorage.setItem('page_auth_hash', hash);
          container.remove();
          const preloadStyle = document.getElementById('auth-preload-style');
          if (preloadStyle) preloadStyle.remove();
          location.reload(); // Reload trang sạch sẽ sau khi đăng nhập thành công
        } else {
          error.style.display = 'block';
          input.value = '';
          input.focus();
        }
      });
    });
  }
})();
