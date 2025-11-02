#!/bin/bash
# Interactive Rasa Client for AFHSync
# Usage: ./chat.sh

read -p "📤 Do you want to publish the trained model to aflabox.ai? (y/n): " publish_choice

if [[ "$publish_choice" == "y" || "$publish_choice" == "Y" ]]; then
  echo "🔄 Publishing via rsync..."
  rsync -avz rasa root@aflabox.ai:/tmps/dockas/default_service/fq
  echo "✅ Publish completed!"
else
  echo "🚫 Skipped publishing."
fi

SERVER_URL="http://95.110.228.29:8734/webhooks/rest/webhook"

# Colors
BLUE='\033[1;34m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Role Selection (simplified)
echo "Choose your role:"
echo "1) Caregiver"
echo "2) AFH Provider" 
echo "3) Service Provider"

read -p "Selection: " role_choice

# Set sender ID and role-specific message
case $role_choice in
  1) 
    SENDER_ID="caregiver-$(date +%s)"
    ROLE_MESSAGE="caregiver"
    
    ;;
  2) 
    SENDER_ID="afh-$(date +%s)" 
    ROLE_MESSAGE="I run an adult family home"
    ;;
  3) 
    SENDER_ID="service-$(date +%s)"
    ROLE_MESSAGE="I'm a service provider"
    ;;
  *) 
    echo "Invalid choice. Exiting."
    exit 1
    ;;
esac

# Function to send message and get response
send_message() {
    local message="$1"
    
    RESPONSE=$(curl -s -X POST "$SERVER_URL" \
        -H "Content-Type: application/json" \
        -d "{\"sender\":\"$SENDER_ID\",\"message\":\"$message\"}")
    
    # Extract bot responses (handle multiple responses)
    echo "$RESPONSE" | jq -r '.[] | select(.text) | .text' | while IFS= read -r line; do
        [[ -n "$line" ]] && echo -e "${GREEN}Bot:${NC} $line"
    done
}

# Send role identification message immediately
echo -e "${YELLOW}Connecting as: $SENDER_ID${NC}"
send_message "$ROLE_MESSAGE"

echo "------------------------------------------------"
echo "Type your messages below (type 'exit' to quit):"

# Chat loop
while true; do
    read -p "$(echo -e ${BLUE}You:${NC} ) " USER_MESSAGE
    
    if [[ "$USER_MESSAGE" == "exit" ]]; then
        echo -e "${GREEN}Bot:${NC} Goodbye!"
        break
    fi
    
    send_message "$USER_MESSAGE"
done