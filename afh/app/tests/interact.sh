#!/bin/bash

BASE_URL="http://localhost:8000"   # <-- change to your actual API base URL
DEFAULT_PHONE="+12065551236"

echo "📱 Do you want to use the default number ($DEFAULT_PHONE)? [y/n]"
read use_default

if [ "$use_default" = "y" ]; then
  PHONE="$DEFAULT_PHONE"
else
  PHONE="+1$((RANDOM % 9000000000 + 1000000000))"
fi

echo "✅ Using phone number: $PHONE"

# function to send a message and parse XML response
send_message() {
  MSG="$1"
  RESPONSE=$(curl -s -X POST "$BASE_URL/webhook/sms" \
    -d "From=$PHONE" \
    -d "Body=$MSG" \
    -d "MessageSid=SM1234567801-$PHONE" \
    -d "AccountSid=AC1234560891-$PHONE")

  STATUS=$?
  if [ $STATUS -ne 0 ]; then
    echo "❌ Error sending message"
    return
  fi

  # Extract <Message>...</Message> content
  REPLY=$(echo "$RESPONSE" | xmllint --xpath "string(//Message)" - 2>/dev/null)


  echo -e "\n💬 API replied:\n$REPLY\n"
}

# Send initial message
send_message "Hello, I am Elijah, what service do you offer?"

# Loop until user quits
while true; do
  echo "✏️ Enter your reply (or type 'quit' to exit):"
  read USER_MSG
  if [ "$USER_MSG" = "quit" ]; then
    echo "👋 Exiting..."
    break
  fi
  send_message "$USER_MSG"
done
