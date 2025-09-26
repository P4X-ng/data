/**
 * HGWS Community Cloud - Unified Navigation System
 * Creates a consistent navigation bar across all dashboards
 */

function createHGWSNav() {
    const navHTML = `
    <div id="hgws-nav" style="
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 9999;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.95) 0%, rgba(118, 75, 162, 0.95) 100%);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        padding: 10px 0;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    ">
        <div style="
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
        ">
            <div style="display: flex; align-items: center;">
                <div style="
                    font-size: 1.5em;
                    font-weight: bold;
                    color: white;
                    margin-right: 30px;
                    cursor: pointer;
                " onclick="window.location.href='/dashboard'">
                    🚀 HGWS Community Cloud
                </div>
                
                <div style="display: flex; gap: 20px;">
                    <a href="/dashboard" class="nav-link" data-tooltip="Main Dashboard">
                        🏠 <span class="nav-text">Home</span>
                    </a>
                    <a href="/static/money-dashboard.html" class="nav-link" data-tooltip="Transparent Money Dashboard">
                        💰 <span class="nav-text">Money</span>
                    </a>
                    <a href="/community/dashboard" class="nav-link" data-tooltip="Community Contributions">
                        🌍 <span class="nav-text">Community</span>
                    </a>
                    <a href="/aws-ridicule" class="nav-link" data-tooltip="Laugh at AWS Pricing (LMFAO!)">
                        🤡 <span class="nav-text">AWS Ridicule</span>
                    </a>
                    <a href="/admin/dashboard" class="nav-link" data-tooltip="Admin Panel">
                        ⚙️ <span class="nav-text">Admin</span>
                    </a>
                </div>
            </div>
            
            <div style="display: flex; gap: 15px; align-items: center;">
                <div class="nav-dropdown">
                    <button class="nav-dropdown-btn" onclick="toggleDropdown()">
                        🔧 <span class="nav-text">Tools</span> ▼
                    </button>
                    <div class="nav-dropdown-content" id="toolsDropdown">
                        <a href="/dashboard/discovery">🔍 Discovery</a>
                        <a href="/dashboard/queue">📊 Queue Monitor</a>
                        <a href="/dashboard/storage">💾 Storage Manager</a>
                        <a href="/price-comparison">🧮 Price Calculator</a>
                        <a href="/static/p4xos-demo.html">⚡ P4XOS Demo</a>
                        <a href="/metrics">📈 Metrics</a>
                        <a href="/api/hosts">🔌 API</a>
                    </div>
                </div>
                
                <div style="
                    background: rgba(0, 255, 136, 0.2);
                    border: 1px solid #00ff88;
                    border-radius: 15px;
                    padding: 5px 15px;
                    font-size: 0.9em;
                    color: #00ff88;
                    cursor: pointer;
                " onclick="checkUserBalance()" id="balanceDisplay">
                    💵 Balance: $0.00
                </div>
            </div>
        </div>
    </div>

    <style>
        body {
            padding-top: 70px !important;
        }
        
        .nav-link {
            color: white !important;
            text-decoration: none !important;
            padding: 8px 15px;
            border-radius: 8px;
            transition: all 0.3s ease;
            position: relative;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .nav-link:hover {
            background: rgba(255, 255, 255, 0.2) !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }
        
        .nav-link.active {
            background: rgba(0, 255, 136, 0.3) !important;
            color: #00ff88 !important;
        }
        
        .nav-dropdown {
            position: relative;
        }
        
        .nav-dropdown-btn {
            background: none;
            border: none;
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 5px;
            font-family: inherit;
        }
        
        .nav-dropdown-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        .nav-dropdown-content {
            display: none;
            position: absolute;
            right: 0;
            top: 100%;
            background: rgba(30, 30, 30, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            padding: 10px 0;
            min-width: 180px;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
        }
        
        .nav-dropdown-content.show {
            display: block;
        }
        
        .nav-dropdown-content a {
            display: block;
            padding: 10px 20px;
            color: white !important;
            text-decoration: none !important;
            transition: background 0.2s ease;
        }
        
        .nav-dropdown-content a:hover {
            background: rgba(102, 126, 234, 0.3);
        }
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {
            #hgws-nav > div {
                flex-direction: column;
                gap: 10px;
                padding: 10px;
            }
            
            .nav-text {
                display: none;
            }
            
            body {
                padding-top: 90px !important;
            }
        }
        
        /* Tooltip styles */
        .nav-link:hover::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: -35px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 0.8em;
            white-space: nowrap;
            z-index: 10000;
        }
    </style>
    `;
    
    // Insert nav at the beginning of body
    document.body.insertAdjacentHTML('afterbegin', navHTML);
    
    // Set active link based on current page
    setActiveNavLink();
    
    // Load user balance
    loadUserBalance();
}

function toggleDropdown() {
    const dropdown = document.getElementById('toolsDropdown');
    dropdown.classList.toggle('show');
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.nav-dropdown')) {
            dropdown.classList.remove('show');
        }
    });
}

function setActiveNavLink() {
    const currentPath = window.location.pathname;
    const links = document.querySelectorAll('.nav-link');
    
    links.forEach(link => {
        const href = link.getAttribute('href');
        if (currentPath === href || (href !== '/dashboard' && currentPath.startsWith(href))) {
            link.classList.add('active');
        }
    });
}

function loadUserBalance() {
    // Try to get balance from localStorage or API
    const storedEmail = localStorage.getItem('hgws_user_email');
    const balanceDisplay = document.getElementById('balanceDisplay');
    
    if (storedEmail) {
        // Try to fetch from API
        fetch(`/api/community/credits/${encodeURIComponent(storedEmail)}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    const balance = (data.total_credits * 0.01).toFixed(2);
                    balanceDisplay.innerHTML = `💵 Balance: $${balance}`;
                    balanceDisplay.style.cursor = 'pointer';
                    balanceDisplay.title = 'Click to view money dashboard';
                    balanceDisplay.onclick = () => window.location.href = '/static/money-dashboard.html';
                }
            })
            .catch(() => {
                // If API fails, show default
                balanceDisplay.innerHTML = '💵 Sign In';
                balanceDisplay.onclick = () => window.location.href = '/static/money-dashboard.html';
            });
    } else {
        balanceDisplay.innerHTML = '💵 Sign In';
        balanceDisplay.onclick = () => window.location.href = '/static/money-dashboard.html';
    }
}

function checkUserBalance() {
    // Navigate to money dashboard
    window.location.href = '/static/money-dashboard.html';
}

// Services panel - small boxy widget top-left
function createServicesPanel() {
    const panel = document.createElement('div');
    panel.id = 'hgws-services-panel';
    panel.style.position = 'fixed';
    panel.style.top = '70px';
    panel.style.left = '10px';
    panel.style.zIndex = '9998';
    panel.style.background = 'rgba(30,30,30,0.95)';
    panel.style.backdropFilter = 'blur(10px)';
    panel.style.border = '1px solid rgba(255,255,255,0.15)';
    panel.style.borderRadius = '10px';
    panel.style.padding = '10px 12px';
    panel.style.minWidth = '220px';
    panel.style.color = 'white';
    panel.style.fontFamily = "'Monaco', 'Menlo', 'Ubuntu Mono', monospace";

    panel.innerHTML = `
      <div style="font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:8px;">
        🧩 Services
      </div>
      <div style="display:flex; flex-direction:column; gap:6px;">
        <a href="/files" style="color:#39FF14; text-decoration:none; display:flex; justify-content:space-between; align-items:center;">
          <span>💾 F3-Infinity</span>
          <span style="border:1px solid #39FF14; border-radius:10px; padding:1px 6px; font-size:11px;">LIVE</span>
        </a>
        <div style="display:flex; justify-content:space-between; opacity:0.8;">
          <span>🖥️ Compute</span>
          <span style="border:1px solid rgba(255,255,255,0.25); border-radius:10px; padding:1px 6px; font-size:11px;">Soon</span>
        </div>
        <div style="display:flex; justify-content:space-between; opacity:0.8;">
          <span>🧠 GPU Cloud</span>
          <span style="border:1px solid rgba(255,255,255,0.25); border-radius:10px; padding:1px 6px; font-size:11px;">Soon</span>
        </div>
        <div style="display:flex; justify-content:space-between; opacity:0.8;">
          <span>🛡️ Zero Trust</span>
          <span style="border:1px solid rgba(255,255,255,0.25); border-radius:10px; padding:1px 6px; font-size:11px;">Soon</span>
        </div>
        <div style="display:flex; justify-content:space-between; opacity:0.8;">
          <span>🏪 Marketplace</span>
          <span style="border:1px solid rgba(255,255,255,0.25); border-radius:10px; padding:1px 6px; font-size:11px;">Soon</span>
        </div>
        <div style="display:flex; justify-content:space-between; opacity:0.8;">
          <span>🌍 Community Cloud</span>
          <span style="border:1px solid rgba(255,255,255,0.25); border-radius:10px; padding:1px 6px; font-size:11px;">Soon</span>
        </div>
      </div>
    `;

    document.body.appendChild(panel);
}

// Auto-initialize when script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { createHGWSNav(); createServicesPanel(); });
} else {
    createHGWSNav();
    createServicesPanel();
}

// Export for manual initialization if needed
window.initHGWSNav = () => { createHGWSNav(); createServicesPanel(); };
