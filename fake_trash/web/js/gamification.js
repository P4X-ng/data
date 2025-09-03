
// PacketFS Gamification System
class PacketFSGame {
    constructor() {
        this.level = parseInt(localStorage.getItem('packetfs_level') || '1');
        this.xp = parseInt(localStorage.getItem('packetfs_xp') || '0');
        this.coins = parseFloat(localStorage.getItem('packetfs_coins') || '0');
        this.achievements = JSON.parse(localStorage.getItem('packetfs_achievements') || '[]');
        this.miningPower = parseFloat(localStorage.getItem('packetfs_mining_power') || '1.0');
    }
    
    initializeGame() {
        console.log('🎮 Initializing PacketFS Game System...');
        this.createGameUI();
        this.startGameLoop();
        this.checkAchievements();
    }
    
    createGameUI() {
        // Create floating game stats panel
        const gameUI = document.createElement('div');
        gameUI.id = 'packetfs-game-ui';
        gameUI.innerHTML = `
            <div style="position: fixed; top: 20px; left: 20px; 
                        background: rgba(0,0,0,0.8); color: white; 
                        padding: 20px; border-radius: 15px; 
                        font-family: monospace; z-index: 1000;
                        backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2);">
                <h3 style="margin: 0 0 15px 0; color: #feca57;">⚡ PacketFS Miner</h3>
                <div>🏆 Level: <span id="game-level">${this.level}</span></div>
                <div>✨ XP: <span id="game-xp">${this.xp}</span>/<span id="game-next-xp">${this.getXPForNextLevel()}</span></div>
                <div>💎 PFS Coins: <span id="game-coins">${this.coins.toFixed(6)}</span></div>
                <div>⚡ Mining Power: <span id="game-power">${this.miningPower.toFixed(1)}x</span></div>
                <div style="margin-top: 15px;">
                    <div style="background: rgba(255,255,255,0.2); height: 10px; border-radius: 5px;">
                        <div id="xp-bar" style="background: linear-gradient(45deg, #4ecdc4, #45b7d1); 
                                               height: 100%; width: ${(this.xp / this.getXPForNextLevel()) * 100}%; 
                                               border-radius: 5px; transition: width 0.3s ease;"></div>
                    </div>
                </div>
                <div style="margin-top: 15px;">
                    <button onclick="window.PacketFSGame.boostMining()" 
                            style="background: linear-gradient(45deg, #ff6b6b, #feca57); 
                                   border: none; color: white; padding: 8px 15px; 
                                   border-radius: 20px; cursor: pointer; font-size: 12px;">
                        🚀 Boost Mining
                    </button>
                    <button onclick="window.PacketFSGame.viewAchievements()" 
                            style="background: linear-gradient(45deg, #4ecdc4, #45b7d1); 
                                   border: none; color: white; padding: 8px 15px; 
                                   border-radius: 20px; cursor: pointer; font-size: 12px; margin-left: 5px;">
                        🏆 Achievements
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(gameUI);
    }
    
    getXPForNextLevel() {
        return this.level * 100;
    }
    
    addXP(amount) {
        this.xp += amount;
        
        // Check for level up
        while (this.xp >= this.getXPForNextLevel()) {
            this.xp -= this.getXPForNextLevel();
            this.level++;
            this.showLevelUp();
            
            // Increase mining power with level
            this.miningPower = 1.0 + (this.level - 1) * 0.1;
        }
        
        this.saveProgress();
        this.updateGameUI();
    }
    
    addCoins(amount) {
        const boostedAmount = amount * this.miningPower;
        this.coins += boostedAmount;
        this.addXP(Math.floor(amount * 10)); // 10 XP per coin
        
        this.saveProgress();
        this.updateGameUI();
        this.showCoinAnimation(boostedAmount);
    }
    
    showLevelUp() {
        const levelUpDiv = document.createElement('div');
        levelUpDiv.innerHTML = `
            <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                        background: linear-gradient(45deg, #feca57, #ff9ff3); color: white;
                        padding: 40px; border-radius: 25px; text-align: center; z-index: 10000;
                        box-shadow: 0 15px 35px rgba(0,0,0,0.6); animation: pulse 1s ease;">
                <h1 style="margin: 0; font-size: 3em;">🚀</h1>
                <h2 style="margin: 10px 0;">LEVEL UP!</h2>
                <p style="font-size: 1.5em; margin: 10px 0;">Level ${this.level}</p>
                <p>Mining Power: ${this.miningPower.toFixed(1)}x</p>
                <button onclick="this.parentElement.parentElement.remove()" 
                        style="background: white; color: #333; border: none; padding: 15px 30px; 
                               border-radius: 25px; cursor: pointer; font-weight: bold; margin-top: 20px;">
                    💎 Continue Mining! 
                </button>
            </div>
        `;
        document.body.appendChild(levelUpDiv);
        
        // Auto-remove after 8 seconds
        setTimeout(() => {
            if (levelUpDiv.parentElement) {
                levelUpDiv.remove();
            }
        }, 8000);
    }
    
    showCoinAnimation(amount) {
        const coinDiv = document.createElement('div');
        coinDiv.innerHTML = `+${amount.toFixed(6)} PFS 💰`;
        coinDiv.style.cssText = `
            position: fixed; top: 100px; right: 100px;
            color: #feca57; font-weight: bold; font-size: 18px;
            pointer-events: none; z-index: 9999;
            animation: coinFloat 2s ease-out forwards;
        `;
        
        // Add CSS animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes coinFloat {
                0% { opacity: 1; transform: translateY(0px); }
                100% { opacity: 0; transform: translateY(-50px); }
            }
        `;
        document.head.appendChild(style);
        
        document.body.appendChild(coinDiv);
        setTimeout(() => coinDiv.remove(), 2000);
    }
    
    boostMining() {
        if (this.coins >= 1.0) {
            this.coins -= 1.0;
            this.miningPower += 0.1;
            
            this.saveProgress();
            this.updateGameUI();
            
            alert('🚀 Mining power boosted! +0.1x multiplier for 1 PFS coin! 💎');
        } else {
            alert('💰 You need at least 1 PFS coin to boost mining power! Keep mining! ⚡');
        }
    }
    
    viewAchievements() {
        const achievementsDiv = document.createElement('div');
        achievementsDiv.innerHTML = `
            <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                        background: rgba(0,0,0,0.95); color: white; padding: 40px; 
                        border-radius: 20px; z-index: 10000; width: 80%; max-width: 500px;
                        max-height: 80%; overflow-y: auto;">
                <h2 style="text-align: center; color: #feca57;">🏆 Achievements</h2>
                ${this.generateAchievementsList()}
                <button onclick="this.parentElement.parentElement.remove()" 
                        style="background: linear-gradient(45deg, #4ecdc4, #45b7d1); 
                               border: none; color: white; padding: 15px 30px; 
                               border-radius: 25px; cursor: pointer; font-weight: bold; 
                               display: block; margin: 20px auto 0;">
                    ✨ Close
                </button>
            </div>
        `;
        document.body.appendChild(achievementsDiv);
    }
    
    generateAchievementsList() {
        const allAchievements = [
            { id: 'first_coin', name: '💰 First Coin', desc: 'Earn your first PFS coin', requirement: () => this.coins >= 0.000001 },
            { id: 'level_5', name: '🚀 Level 5', desc: 'Reach level 5', requirement: () => this.level >= 5 },
            { id: 'level_10', name: '⚡ Level 10', desc: 'Reach level 10', requirement: () => this.level >= 10 },
            { id: 'hundred_coins', name: '💎 Century', desc: 'Earn 100 PFS coins', requirement: () => this.coins >= 100 },
            { id: 'power_miner', name: '🔥 Power Miner', desc: 'Achieve 3x mining power', requirement: () => this.miningPower >= 3.0 },
            { id: 'dedicated_miner', name: '⭐ Dedicated', desc: 'Mine for 1 hour continuously', requirement: () => true }, // Time-based
            { id: 'social_miner', name: '🌟 Social', desc: 'Refer 10 friends', requirement: () => (window.PacketFSViral?.referralCount || 0) >= 10 }
        ];
        
        let html = '<div style="display: grid; gap: 15px;">';
        
        allAchievements.forEach(achievement => {
            const unlocked = achievement.requirement();
            const status = unlocked ? '✅' : '🔒';
            const style = unlocked ? 'color: #2ecc71;' : 'color: #95a5a6;';
            
            html += `
                <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; ${style}">
                    <div style="font-size: 1.2em; margin-bottom: 5px;">${status} ${achievement.name}</div>
                    <div style="font-size: 0.9em; opacity: 0.8;">${achievement.desc}</div>
                </div>
            `;
            
            if (unlocked && !this.achievements.includes(achievement.id)) {
                this.achievements.push(achievement.id);
                this.showAchievementUnlock(achievement);
            }
        });
        
        html += '</div>';
        return html;
    }
    
    showAchievementUnlock(achievement) {
        const unlockDiv = document.createElement('div');
        unlockDiv.innerHTML = `
            <div style="position: fixed; top: 20px; right: 20px; 
                        background: linear-gradient(45deg, #2ecc71, #27ae60); 
                        color: white; padding: 20px; border-radius: 15px; 
                        box-shadow: 0 5px 15px rgba(0,0,0,0.3); z-index: 9999;
                        animation: slideInRight 0.5s ease;">
                🏆 Achievement Unlocked!<br>
                <strong>${achievement.name}</strong><br>
                <small>${achievement.desc}</small>
            </div>
        `;
        document.body.appendChild(unlockDiv);
        
        setTimeout(() => unlockDiv.remove(), 5000);
    }
    
    updateGameUI() {
        const elements = {
            'game-level': this.level,
            'game-xp': this.xp,
            'game-next-xp': this.getXPForNextLevel(),
            'game-coins': this.coins.toFixed(6),
            'game-power': this.miningPower.toFixed(1) + 'x'
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
        
        // Update XP bar
        const xpBar = document.getElementById('xp-bar');
        if (xpBar) {
            xpBar.style.width = `${(this.xp / this.getXPForNextLevel()) * 100}%`;
        }
    }
    
    saveProgress() {
        localStorage.setItem('packetfs_level', this.level.toString());
        localStorage.setItem('packetfs_xp', this.xp.toString());
        localStorage.setItem('packetfs_coins', this.coins.toString());
        localStorage.setItem('packetfs_mining_power', this.miningPower.toString());
        localStorage.setItem('packetfs_achievements', JSON.stringify(this.achievements));
    }
    
    startGameLoop() {
        // Passive income generation
        setInterval(() => {
            const passiveIncome = 0.000001 * this.miningPower; // Very small passive income
            this.addCoins(passiveIncome);
        }, 5000); // Every 5 seconds
    }
    
    checkAchievements() {
        // Check achievements periodically
        setInterval(() => {
            this.generateAchievementsList(); // This will trigger unlock notifications
            this.saveProgress();
        }, 10000); // Every 10 seconds
    }
}

// Initialize game system
const packetfsGame = new PacketFSGame();

// Make available globally
window.PacketFSGame = packetfsGame;

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => packetfsGame.initializeGame());
} else {
    packetfsGame.initializeGame();
}
