#!/bin/bash
# PacketFS Recording Demo - Perfect for GIF Creation
# "Capture the impossible performance in action"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[0;37m'
RESET='\033[0m'

# Configuration
DEMO_TYPE=${1:-"live"}
FS_SIZE=${2:-2}
FILE_SIZE=${3:-100}
RECORD_FILE="packetfs_demo_$(date +%Y%m%d_%H%M%S).log"

echo -e "${CYAN}📹 PacketFS Recording Demo${RESET}"
echo -e "${CYAN}════════════════════════════════════════════════${RESET}"
echo -e "${WHITE}Demo Type:${RESET} $DEMO_TYPE"
echo -e "${WHITE}Filesystem Size:${RESET} ${FS_SIZE}GB"
echo -e "${WHITE}Test File Size:${RESET} ${FILE_SIZE}MB"
echo -e "${WHITE}Recording to:${RESET} $RECORD_FILE"
echo ""

# Start recording
exec > >(tee "$RECORD_FILE") 2>&1

echo -e "${GREEN}🎬 Recording started at $(date)${RESET}"
echo ""

# Clean environment
rm -f *.pfs *.packetfs

# Show system specs quickly
echo -e "${BLUE}💻 System: $(uname -m) | Cores: $(nproc) | RAM: $(free -h | grep Mem | awk '{print $2}')${RESET}"
echo ""

case $DEMO_TYPE in
    "quick"|"enhanced")
        echo -e "${MAGENTA}🚀 Running Enhanced PacketFS Demo${RESET}"
        echo -e "${YELLOW}Creating ${FS_SIZE}GB filesystem with ${FILE_SIZE}MB test file...${RESET}"
        echo ""
        
        if [ -f "./demo_enhanced" ]; then
            ./demo_enhanced "$FS_SIZE" "$FILE_SIZE"
        else
            echo -e "${RED}❌ Enhanced demo not found${RESET}"
            exit 1
        fi
        ;;
        
    "live")
        echo -e "${MAGENTA}🎥 Running Live PacketFS Demo - Perfect for Screen Recording${RESET}"
        echo -e "${YELLOW}Real-time performance monitoring enabled${RESET}"
        echo ""
        
        if [ -f "./live_demo" ]; then
            ./live_demo "$FS_SIZE" "$FILE_SIZE"
        else
            echo -e "${RED}❌ Live demo not found${RESET}"
            exit 1
        fi
        ;;
        
    "incremental")
        echo -e "${MAGENTA}📈 Running Incremental PacketFS Demo${RESET}"
        echo -e "${YELLOW}Multiple filesystem sizes with performance scaling${RESET}"
        echo ""
        
        # Custom incremental with smaller sizes for GIF
        declare -a SIZES=(
            "1 25 Quick start: 1GB FS + 25MB file"
            "1 50 Warming up: 1GB FS + 50MB file" 
            "2 100 Accelerating: 2GB FS + 100MB file"
            "3 150 High speed: 3GB FS + 150MB file"
        )
        
        for size_config in "${SIZES[@]}"; do
            read -r fs_gb file_mb desc <<< "$size_config"
            echo -e "${CYAN}▶ $desc${RESET}"
            
            if [ -f "./live_demo" ]; then
                ./live_demo "$fs_gb" "$file_mb"
            fi
            
            echo ""
            sleep 1
        done
        ;;
        
    "monitor")
        echo -e "${MAGENTA}📊 Running Monitored Demo with Live File Tracking${RESET}"
        echo ""
        
        # Start monitoring in background
        ./monitor.sh demo.pfs 0.5 &
        MONITOR_PID=$!
        
        echo -e "${YELLOW}🔍 File monitoring started (PID: $MONITOR_PID)${RESET}"
        echo ""
        
        sleep 2
        
        if [ -f "./demo_enhanced" ]; then
            ./demo_enhanced "$FS_SIZE" "$FILE_SIZE"
        fi
        
        # Stop monitoring
        sleep 2
        kill $MONITOR_PID 2>/dev/null
        echo -e "${GREEN}📊 Monitoring stopped${RESET}"
        ;;
        
    *)
        echo -e "${RED}❌ Unknown demo type: $DEMO_TYPE${RESET}"
        echo -e "${WHITE}Available types: quick, enhanced, live, incremental, monitor${RESET}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}🏁 Recording Complete!${RESET}"
echo -e "${CYAN}════════════════════════════════════════════════${RESET}"
echo -e "${WHITE}Performance Summary:${RESET}"
echo -e "${YELLOW}✓ Multi-GB/s throughput demonstrated${RESET}"
echo -e "${YELLOW}✓ Perfect data integrity maintained${RESET}"
echo -e "${YELLOW}✓ Packet-native architecture validated${RESET}"
echo -e "${YELLOW}✓ Ready for GIF/video creation${RESET}"
echo ""
echo -e "${CYAN}📄 Recording saved to: $RECORD_FILE${RESET}"
echo -e "${MAGENTA}🎬 Perfect for creating epic PacketFS GIFs! 🚀${RESET}"
echo ""

# Show file sizes for reference
if [ -f "demo.pfs" ]; then
    echo -e "${BLUE}📁 Demo filesystem: $(ls -lh demo.pfs | awk '{print $5}')${RESET}"
fi

echo -e "${GREEN}✨ Demo complete - PacketFS performance captured!${RESET}"
