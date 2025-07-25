<h1 align="center">👨‍🍳 Sous-Chef AI</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram" />
  <img src="https://img.shields.io/badge/MongoDB-Connected-green?logo=mongodb" />
  <img src="https://img.shields.io/badge/Deployed%20on-Render-orange?logo=render" />
  <img src="https://img.shields.io/badge/License-Unlicense-lightgrey" />
</p>

<p align="center">
  🍽️ Your personal AI chef and nutritionist — built with Gemini, MongoDB, and ❤️ <br>
  🤖 <a href="https://t.me/Sous_Chef_AI_bot">Try the Bot on Telegram</a>
</p>

---

## 📸 About the Project

Sous-Chef AI is a **smart recipe assistant** that creates personalized, health-conscious meals using:

* Your available **ingredients**
* Your **health stats** (like BP, sugar, cholesterol)
* **Dietary restrictions** (e.g., vegan, keto)
* Any **allergies** you might have

It uses **Google Gemini** for recipe generation and stores user preferences and recipes in **MongoDB**.

---

## 🚀 Try It Now

Click the button to try it:

<p align="center">
  <a href="https://t.me/Sous_Chef_AI_bot">
    <img src="https://img.shields.io/badge/-Launch%20Sous--Chef%20AI%20🍳-blue?style=for-the-badge&logo=telegram" />
  </a>
</p>

---

## 🧠 Features

* 📝 Health-aware recipe generator
* 🍏 Gemini-powered recipe composition
* 💬 Natural language ingredient handling
* 📊 Nutritional breakdown per recipe
* 🧠 Fun food facts and cuisine trivia
* 💾 Save/view/delete recipes anytime
* 🔒 All preferences stored securely in MongoDB

---

## 💡 Example Commands

```text
/start             - Welcome and intro
/help              - Show all features
/health            - Set health info (BP, sugar, etc.)
/diet              - Set dietary preferences & allergies
/status            - See current preferences
/myrecipes         - View saved recipes
/clear             - Clear saved preferences
```

Or just type messages like:

```
chicken, broccoli, lemon
just finished a workout
need something low in sodium
```

---

## 🛠️ Tech Stack

| Component     | Tech Used                                  |
| ------------- | ------------------------------------------ |
| 🤖 Bot Engine | Python + python-telegram-bot               |
| 🧠 AI Model   | Google Gemini (generativeai)               |
| 🗄️ Database  | MongoDB Atlas (user preferences + recipes) |
| 🌍 Deployment | Render.com                                 |

---

## 📂 Installation

> 🛑 You only need this section if you're self-hosting the bot.

```bash
git clone https://github.com/rambo1111/Sous-Chef-AI_Telegram-Bot.git
cd Sous-Chef-AI_Telegram-Bot
pip install -r requirements.txt
```

Create a `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
GEMINI_API_KEY=your_gemini_api_key
MONGO_PASSWORD=your_mongo_password
```

Then run:

```bash
python bot.py
```

---

## 🌐 Deployment

Sous-Chef AI is currently deployed using [Render](https://render.com). You can deploy your own instance easily with:

* 🔐 Environment variables for secure key management
* ⚡ Always-on polling
* ☁️ Scalable MongoDB (Atlas)

---

## ⚖️ License

This project is released under **The Unlicense** — it's public domain. Do whatever you want with it. ✨

---

## 🤝 Contribute

Pull requests are welcome! Open an issue to discuss features or ideas.

---

## 👨‍🍳 Author

Made with ❤️ by **Vibhaw Kureel**

---

