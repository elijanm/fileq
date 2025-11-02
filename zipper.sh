zip -r a.zip . -x "venv/*" "ui/node_modules/*" "__pycache__/*"
curl bashupload.com -T a.zip