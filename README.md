CARA MEMASANGNYA BOT 

1. Update & Upgrade Termux
```
pkg update && pkg upgrade -y
```
2. Install Git
```
pkg install git -y
```
3. Clone this repo
```
https://github.com/Yoochu123/bot-kasir-telegram
```
4. Open the folder
```
cd bot-kasir-telegram
```
5. Install Semua Library yang Dibutuhkan
```
# Untuk Windows (Command Prompt)
copy .env.example .env

# Untuk Linux/macOS/Git Bash
cp .env.example .env
```
6. Install Semua Library yang Dibutuhkan
```
pip install -r requirements.txt
```
7. Run the script
```
python rekap.py
