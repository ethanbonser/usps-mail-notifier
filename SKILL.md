---
name: usps-mail-notifier
description: Automates USPS Informed Delivery notifications via Telegram. Scans for USPS emails, extracts mail images, and sends them to a Telegram bot. Use when the user wants to check their physical mail status manually from their PC with a one-click notification.
---

# USPS Informed Delivery Notifier

This skill provides a manual way to check for today's physical mail images and send them to your Telegram.

## Setup Instructions

### 1. Gmail Setup
Gmail requires an **App Password** to allow a script to connect.
- Go to [Google Account Security](https://myaccount.google.com/security).
- Enable **2-Step Verification**.
- Search for **App Passwords** in the search bar.
- Create a new app (e.g., "USPS Notifier") and copy the 16-character code.

### 2. Telegram Setup
- Message [@BotFather](https://t.me/botfather) to create a new bot. Copy the **API Token**.
- Message [@userinfobot](https://t.me/userinfobot) to get your **Chat ID**.

### 3. Configure the Script
Open `usps-mail-notifier/scripts/check_mail.py` and replace the following variables:
- `GMAIL_USER`: Your Gmail address.
- `GMAIL_APP_PASSWORD`: Your 16-character Google App Password.
- `TELEGRAM_BOT_TOKEN`: Your Bot API token.
- `TELEGRAM_CHAT_ID`: Your Telegram Chat ID.

### 4. Install Dependencies
Double-click `usps-mail-notifier/assets/setup.bat` to install the `requests` library.

### 5. Check Your Mail
- Double-click `usps-mail-notifier/assets/Run_USPS_Notifier.bat` whenever you want to perform a **one-time** check for mail.
- Double-click `usps-mail-notifier/assets/Start_Background_Listener.bat` to start the **background listener** that supports Telegram commands (`/check`, `/clear`, etc.) and automatic daily checks.

## Troubleshooting
- **No mail images found?** The script only checks for USPS emails sent **today**.
- **Login error?** Ensure you are using an "App Password," not your regular Gmail password.
- **Python not found?** Ensure Python is installed and added to your system PATH.
