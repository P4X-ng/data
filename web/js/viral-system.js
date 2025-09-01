
// PacketFS Viral Sharing System
class PacketFSViral {
    constructor() {
        this.referralCode = this.getReferralCode();
        this.referralCount = parseInt(localStorage.getItem('packetfs_referrals') || '0');
        this.bonusEarnings = parseFloat(localStorage.getItem('packetfs_bonus') || '0');
    }
    
    getReferralCode() {
        let code = localStorage.getItem('packetfs_referral_code');
        if (!code) {
            code = this.generateReferralCode();
            localStorage.setItem('packetfs_referral_code', code);
        }
        return code;
    }
    
    generateReferralCode() {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        let result = 'PFS';
        for (let i = 0; i < 5; i++) {
            result += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return result;
    }
    
    trackReferral(referrerCode) {
        if (referrerCode && referrerCode !== this.referralCode) {
            // Track this as a successful referral
            console.log(`🌟 Referred by: ${referrerCode}`);
            
            // Store referrer for bonus payments
            localStorage.setItem('packetfs_referred_by', referrerCode);
            
            // Send tracking event
            this.sendReferralEvent(referrerCode);
            
            // Show welcome bonus
            this.showReferralWelcome(referrerCode);
        }
    }
    
    sendReferralEvent(referrerCode) {
        // In production, this would send to analytics/backend
        if (typeof gtag !== 'undefined') {
            gtag('event', 'referral_signup', {
                'event_category': 'PacketFS',
                'event_label': referrerCode,
                'value': 1
            });
        }
    }
    
    showReferralWelcome(referrerCode) {
        const welcomeDiv = document.createElement('div');
        welcomeDiv.innerHTML = `
            <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                        background: linear-gradient(45deg, #ff6b6b, #feca57); color: white;
                        padding: 30px; border-radius: 20px; text-align: center; z-index: 10000;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <h2>🎉 Welcome Bonus! 🎉</h2>
                <p>You were referred by <strong>${referrerCode}</strong>!</p>
                <p>🎁 You get <strong>+50% earning boost</strong> for 24 hours!</p>
                <p>💰 Your referrer gets <strong>10% of your earnings</strong> forever!</p>
                <button onclick="this.parentElement.parentElement.remove()" 
                        style="background: white; color: #333; border: none; padding: 10px 20px; 
                               border-radius: 25px; cursor: pointer; font-weight: bold;">
                    🚀 Let's Start Earning! 💎
                </button>
            </div>
        `;
        document.body.appendChild(welcomeDiv);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (welcomeDiv.parentElement) {
                welcomeDiv.remove();
            }
        }, 10000);
    }
    
    shareOnPlatform(platform) {
        const shareUrl = `https://packetfs.global?ref=${this.referralCode}`;
        const shareText = '🚀 I just turned my browser into a SUPER-CPU and I\'m earning crypto! Join PacketFS and start earning too! 💎';
        
        const urls = {
            twitter: `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${shareUrl}&hashtags=PacketFS,Crypto,SuperCPU`,
            facebook: `https://www.facebook.com/sharer/sharer.php?u=${shareUrl}`,
            reddit: `https://reddit.com/submit?url=${shareUrl}&title=${encodeURIComponent(shareText)}`,
            telegram: `https://t.me/share/url?url=${shareUrl}&text=${encodeURIComponent(shareText)}`,
            whatsapp: `https://wa.me/?text=${encodeURIComponent(shareText + ' ' + shareUrl)}`,
            linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${shareUrl}`
        };
        
        if (urls[platform]) {
            window.open(urls[platform], '_blank', 'width=600,height=400');
            
            // Track share event
            if (typeof gtag !== 'undefined') {
                gtag('event', 'social_share', {
                    'event_category': 'PacketFS',
                    'event_label': platform,
                    'value': 1
                });
            }
        }
    }
    
    copyReferralLink() {
        const shareUrl = `https://packetfs.global?ref=${this.referralCode}`;
        const shareText = `🚀 Turn your browser into a SUPER-CPU and earn crypto! PacketFS is revolutionary! ${shareUrl}`;
        
        navigator.clipboard.writeText(shareText).then(() => {
            this.showCopySuccess();
        });
    }
    
    showCopySuccess() {
        const notification = document.createElement('div');
        notification.innerHTML = '📋 Referral link copied! Share it everywhere! 🚀';
        notification.style.cssText = `
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
            background: #2ecc71; color: white; padding: 15px 30px; border-radius: 25px;
            font-weight: bold; z-index: 9999; animation: slideUp 0.3s ease;
        `;
        document.body.appendChild(notification);
        
        setTimeout(() => notification.remove(), 3000);
    }
    
    updateReferralStats() {
        // Simulate referral growth
        if (Math.random() < 0.1) { // 10% chance each update
            this.referralCount++;
            this.bonusEarnings += Math.random() * 0.5;
            
            localStorage.setItem('packetfs_referrals', this.referralCount.toString());
            localStorage.setItem('packetfs_bonus', this.bonusEarnings.toFixed(6));
            
            // Show referral notification
            if (this.referralCount % 5 === 0) {
                this.showReferralMilestone();
            }
        }
    }
    
    showReferralMilestone() {
        const milestone = document.createElement('div');
        milestone.innerHTML = `
            <div style="position: fixed; top: 50px; right: 20px; 
                        background: linear-gradient(45deg, #4ecdc4, #45b7d1); 
                        color: white; padding: 20px; border-radius: 15px; 
                        box-shadow: 0 5px 15px rgba(0,0,0,0.3); z-index: 9999;">
                🎉 Referral Milestone! 🎉<br>
                <strong>${this.referralCount} friends joined!</strong><br>
                💰 Bonus: +$${this.bonusEarnings.toFixed(2)}
            </div>
        `;
        document.body.appendChild(milestone);
        
        setTimeout(() => milestone.remove(), 5000);
    }
    
    initializeViralFeatures() {
        // Check for referral code in URL
        const urlParams = new URLSearchParams(window.location.search);
        const referrerCode = urlParams.get('ref');
        
        if (referrerCode) {
            this.trackReferral(referrerCode);
        }
        
        // Start referral stats updates
        setInterval(() => {
            this.updateReferralStats();
        }, 30000); // Every 30 seconds
        
        console.log(`🌟 Viral system initialized. Your referral code: ${this.referralCode}`);
    }
}

// Initialize viral system
const packetfsViral = new PacketFSViral();
packetfsViral.initializeViralFeatures();

// Make available globally
window.PacketFSViral = packetfsViral;
