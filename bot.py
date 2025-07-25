import os
import logging
import json
import re
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import google.generativeai as genai
from pymongo import MongoClient
from bson.objectid import ObjectId

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Bot and API Configuration ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MONGO_PASSWORD = os.environ.get("MONGO_PASSWORD")

# --- MongoDB Setup ---
try:
    if not MONGO_PASSWORD:
        raise ValueError("MONGO_PASSWORD environment variable not set!")
    
    uri = f"mongodb+srv://rambo:{MONGO_PASSWORD}@sous-chef-ai-telegram-b.wc6o1qa.mongodb.net/?retryWrites=true&w=majority&appName=Sous-Chef-AI-Telegram-Bot"
    client = MongoClient(uri)
    
    # Ping to confirm connection
    client.admin.command('ping')
    db = client['sous_chef_ai_db']
    users_collection = db['users']
    recipes_collection = db['recipes']
    logger.info("Successfully connected to MongoDB!")

except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    # If DB connection fails, the bot can still run with in-memory storage for the session.
    client = None
    users_collection = None
    recipes_collection = None
# --- End MongoDB Setup ---


# Dynamic Loading Messages
LOADING_MESSAGES = [
    "🍳 Prepping the kitchen...",
    "🥕 Sharpening my knives...",
    "🔥 Preheating the oven...",
    "🤖 Consulting with the master chefs...",
    "📚 Skimming through my cookbook...",
    "🌿 Gathering fresh herbs..."
]

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# User data cache (data will be loaded from MongoDB into this dictionary)
user_data = {}

class RecipeBot:
    def __init__(self):
        self.health_options = {
            'blood_pressure': {
                'normal': 'Normal (120/80)',
                'elevated': 'Elevated (120-129/80)',
                'high_stage1': 'High Stage 1 (130-139/80-89)',
                'high_stage2': 'High Stage 2 (140+/90+)'
            },
            'blood_sugar': {
                'normal': 'Normal (70-100 mg/dL)',
                'prediabetic': 'Prediabetic (100-125 mg/dL)',
                'diabetic': 'Diabetic (126+ mg/dL)'
            },
            'cholesterol': {
                'normal': 'Normal (Less than 200 mg/dL)',
                'borderline': 'Borderline (200-239 mg/dL)',
                'high': 'High (240+ mg/dL)'
            }
        }

    def create_recipe_prompt(self, ingredients, health_stats, dietary_restrictions, allergies):
        """Create a detailed prompt for the AI based on user inputs"""
        
        prompt = f"""
        You are a professional nutritionist and chef. Create a detailed, healthy recipe using the following information:

        AVAILABLE INGREDIENTS: {ingredients}

        HEALTH CONSIDERATIONS:
        """
        
        if health_stats.get('blood_pressure'):
            prompt += f"- Blood Pressure: {health_stats['blood_pressure']} (recommend low-sodium options)\n"
        
        if health_stats.get('blood_sugar'):
            prompt += f"- Blood Sugar Level: {health_stats['blood_sugar']} (recommend low-glycemic options)\n"
        
        if health_stats.get('cholesterol'):
            prompt += f"- Cholesterol Level: {health_stats['cholesterol']} (recommend heart-healthy options)\n"
        
        if dietary_restrictions:
            prompt += f"- Dietary Restrictions: {dietary_restrictions}\n"
        
        if allergies:
            prompt += f"- Allergies: {allergies}\n"
        
        prompt += """
        IMPORTANT: Please respond ONLY with valid JSON format. No additional text, explanations, or formatting outside the JSON structure.

        Provide the response in this exact JSON structure:
        {
            "recipe": {
                "name": "Recipe Name",
                "prep_time": "X minutes",
                "cook_time": "X minutes",
                "total_time": "X minutes",
                "servings": "X servings",
                "ingredients": [
                    "ingredient 1 with measurement",
                    "ingredient 2 with measurement"
                ],
                "instructions": [
                    "Step 1 detailed instruction",
                    "Step 2 detailed instruction"
                ],
                "health_tips": [
                    "Health tip 1",
                    "Health tip 2"
                ],
                "storage": "Storage instructions"
            },
            "nutritional_info": {
                "calories_per_serving": "X calories",
                "protein": "X grams",
                "carbs": "X grams",
                "fat": "X grams",
                "fiber": "X grams",
                "sodium": "X mg",
                "health_benefits": [
                    "Health benefit 1",
                    "Health benefit 2"
                ]
            },
            "recipe_facts": {
                "cuisine_type": "Cuisine type",
                "difficulty": "Easy/Medium/Hard",
                "meal_type": "Breakfast/Lunch/Dinner/Snack",
                "dietary_tags": ["tag1", "tag2"],
                "fun_facts": [
                    "Interesting fact 1 about ingredients or cooking method",
                    "Interesting fact 2 about nutritional benefits"
                ]
            }
        }

        Make sure the recipe is tailored to the health conditions and dietary needs mentioned above.
        """
        
        return prompt

    def escape_markdown(self, text):
        """Escape special Markdown characters"""
        if not text:
            return ""
        # Escape special Markdown characters
        special_chars = ['*', '_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def format_recipe_message(self, recipe_data):
        """Format recipe data for Telegram message"""
        recipe = recipe_data['recipe']
        
        message = f"🍳 *{self.escape_markdown(recipe['name'])}*\n\n"
        
        # Recipe info
        message += f"⏱️ *Prep:* {self.escape_markdown(recipe['prep_time'])}\n"
        message += f"🔥 *Cook:* {self.escape_markdown(recipe['cook_time'])}\n"
        message += f"⏰ *Total:* {self.escape_markdown(recipe['total_time'])}\n"
        message += f"🍽️ *Serves:* {self.escape_markdown(recipe['servings'])}\n\n"
        
        # Ingredients
        message += "🥘 *Ingredients:*\n"
        for ingredient in recipe['ingredients']:
            message += f"• {self.escape_markdown(ingredient)}\n"
        message += "\n"
        
        # Instructions
        message += "👨‍🍳 *Instructions:*\n"
        for i, instruction in enumerate(recipe['instructions'], 1):
            message += f"{i}\\. {self.escape_markdown(instruction)}\n"
        message += "\n"
        
        # Health tips
        if recipe.get('health_tips'):
            message += "💡 *Health Tips:*\n"
            for tip in recipe['health_tips']:
                message += f"• {self.escape_markdown(tip)}\n"
            message += "\n"
        
        # Storage
        if recipe.get('storage'):
            message += f"🗄️ *Storage:* {self.escape_markdown(recipe['storage'])}\n"
        
        return message

    def format_nutrition_message(self, recipe_data):
        """Format nutrition data for Telegram message"""
        nutrition = recipe_data['nutritional_info']
        
        message = "📊 *Nutritional Information*\n"
        message += "Per serving breakdown:\n\n"
        
        message += f"🔥 *Calories:* {self.escape_markdown(nutrition['calories_per_serving'])}\n"
        message += f"🥩 *Protein:* {self.escape_markdown(nutrition['protein'])}\n"
        message += f"🍞 *Carbs:* {self.escape_markdown(nutrition['carbs'])}\n"
        message += f"🥑 *Fat:* {self.escape_markdown(nutrition['fat'])}\n"
        message += f"🌾 *Fiber:* {self.escape_markdown(nutrition['fiber'])}\n"
        message += f"🧂 *Sodium:* {self.escape_markdown(nutrition['sodium'])}\n\n"
        
        if nutrition.get('health_benefits'):
            message += "🌟 *Health Benefits:*\n"
            for benefit in nutrition['health_benefits']:
                message += f"• {self.escape_markdown(benefit)}\n"
        
        return message

    def format_facts_message(self, recipe_data):
        """Format recipe facts for Telegram message"""
        facts = recipe_data['recipe_facts']
        
        message = "🧠 *Recipe Facts*\n\n"
        
        message += f"🌍 *Cuisine:* {self.escape_markdown(facts['cuisine_type'])}\n"
        message += f"📈 *Difficulty:* {self.escape_markdown(facts['difficulty'])}\n"
        message += f"🍽️ *Meal Type:* {self.escape_markdown(facts['meal_type'])}\n"
        
        if facts.get('dietary_tags'):
            tags = ', '.join(facts['dietary_tags'])
            message += f"🏷️ *Tags:* {self.escape_markdown(tags)}\n\n"
        
        if facts.get('fun_facts'):
            message += "🎯 *Did You Know?*\n"
            for fact in facts['fun_facts']:
                message += f"💡 {self.escape_markdown(fact)}\n"
        
        return message

bot = RecipeBot()

# --- Database Functions ---

def save_user_preferences(user_id, prefs):
    """Save or update user preferences in MongoDB."""
    if users_collection is None:
        logger.warning("MongoDB not connected. Skipping user preferences save.")
        return
    try:
        # Filter out temporary keys like 'setting' or 'last_recipe' before saving
        prefs_to_save = {k: v for k, v in prefs.items() if k not in ['setting', 'last_recipe', '_id']}
        users_collection.update_one(
            {'_id': user_id},
            {'$set': prefs_to_save},
            upsert=True
        )
        logger.info(f"Saved preferences for user {user_id} to MongoDB.")
    except Exception as e:
        logger.error(f"Could not save preferences for user {user_id}: {e}")

def save_recipe(user_id, recipe_data):
    """Save a generated recipe to MongoDB."""
    if recipes_collection is None:
        logger.warning("MongoDB not connected. Skipping recipe save.")
        return
    try:
        recipe_to_save = recipe_data.copy()
        recipe_to_save['user_id'] = user_id
        recipes_collection.insert_one(recipe_to_save)
        logger.info(f"Saved recipe for user {user_id} to MongoDB.")
    except Exception as e:
        logger.error(f"Could not save recipe for user {user_id}: {e}")

def delete_recipe(recipe_id):
    """Delete a recipe from MongoDB by its _id."""
    if recipes_collection is None:
        logger.warning("MongoDB not connected. Cannot delete recipe.")
        return False
    try:
        result = recipes_collection.delete_one({'_id': ObjectId(recipe_id)})
        if result.deleted_count > 0:
            logger.info(f"Deleted recipe {recipe_id} from MongoDB.")
            return True
        else:
            logger.warning(f"Recipe {recipe_id} not found for deletion.")
            return False
    except Exception as e:
        logger.error(f"Could not delete recipe {recipe_id}: {e}")
        return False

def load_user_preferences(user_id):
    """Load user preferences from MongoDB into the local cache."""
    # If user data is already in the cache, no need to load again.
    if user_id in user_data:
        return user_data[user_id]
    
    if users_collection is None:
        logger.warning("MongoDB not connected. Using temporary in-memory storage.")
        user_data[user_id] = {}
        return user_data[user_id]
        
    try:
        prefs = users_collection.find_one({'_id': user_id})
        if prefs:
            user_data[user_id] = prefs
            logger.info(f"Loaded preferences for user {user_id} from MongoDB.")
        else:
            # No preferences found in DB, create an empty entry in the cache.
            user_data[user_id] = {}
            logger.info(f"No preferences found for user {user_id}. Creating new profile.")
        return user_data[user_id]
    except Exception as e:
        logger.error(f"Could not load preferences for user {user_id}: {e}")
        # On error, use an empty dictionary to prevent crashes
        user_data[user_id] = {}
        return user_data[user_id]

def get_user_recipes(user_id):
    """Fetch all recipes for a given user from MongoDB."""
    if recipes_collection is None:
        logger.warning("MongoDB not connected. Cannot fetch recipes.")
        return []
    try:
        # Find all recipes for the user_id and return them as a list
        recipes = list(recipes_collection.find({'user_id': user_id}))
        logger.info(f"Found {len(recipes)} recipes for user {user_id}.")
        return recipes
    except Exception as e:
        logger.error(f"Could not fetch recipes for user {user_id}: {e}")
        return []

# --- Telegram Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    # Load user data at the start of the conversation
    load_user_preferences(user.id)
    
    welcome_message = f"""
🍳 *Welcome to Sous-Chef AI, {user.first_name}!*

I'm your personal AI nutritionist and chef! I can help you create healthy, personalized recipes based on:

🥕 *Your ingredients*
🏥 *Your health conditions*
🌱 *Your dietary preferences*
🚫 *Your allergies*

*How to use me:*
• Just send me your ingredients or describe your situation
• Use /health to set your health information
• Use /diet to set dietary preferences
• Use /help for more options

*Example messages:*
• "chicken, broccoli, quinoa"
• "just finished workout, need protein"
• "feeling sick, what should I eat?"
• "need quick healthy lunch"

Let's start cooking! 🎉
    """
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """
🆘 *Sous-Chef AI Help*

*Commands:*
/start - Start the bot
/help - Show this help message
/health - Set your health information
/diet - Set dietary preferences and allergies
/myrecipes - View your saved recipes
/clear - Clear all your saved preferences
/status - View your current preferences

*How to create recipes:*
Just send me a message with:
• Ingredients you have
• Your cooking situation
• What you're feeling like eating

*Examples:*
"salmon, asparagus, lemon"
"need energy boost breakfast"
"quick dinner for weight loss"
"comfort food for cold day"

I'll create a personalized recipe just for you! 🍽️
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle health information setup"""
    user_id = update.effective_user.id
    load_user_preferences(user_id)
    
    keyboard = [
        [InlineKeyboardButton("Blood Pressure", callback_data="health_bp")],
        [InlineKeyboardButton("Blood Sugar", callback_data="health_bs")],
        [InlineKeyboardButton("Cholesterol", callback_data="health_chol")],
        [InlineKeyboardButton("Done", callback_data="health_done")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏥 *Health Information Setup*\n\nSelect which health information you'd like to set:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def diet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dietary preferences setup"""
    user_id = update.effective_user.id
    load_user_preferences(user_id)
    
    await update.message.reply_text(
        "🌱 *Dietary Preferences Setup*\n\n"
        "Please send me your dietary restrictions (e.g., vegetarian, vegan, keto, paleo, gluten-free)\n"
        "Or type 'none' if you don't have any restrictions.",
        parse_mode='Markdown'
    )
    
    user_data[user_id]['setting'] = 'dietary_restrictions'

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear user preferences from cache and database."""
    user_id = update.effective_user.id
    
    # Clear from local cache
    if user_id in user_data:
        del user_data[user_id]
        
    # Clear from MongoDB
    if users_collection is not None:
        try:
            result = users_collection.delete_one({'_id': user_id})
            if result.deleted_count > 0:
                logger.info(f"Cleared preferences for user {user_id} from MongoDB.")
        except Exception as e:
            logger.error(f"Error clearing preferences for user {user_id} from MongoDB: {e}")

    await update.message.reply_text(
        "✅ All your preferences have been cleared!\n"
        "You can set them again using /health and /diet commands."
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's current preferences."""
    user_id = update.effective_user.id
    data = load_user_preferences(user_id)
    
    # Check if there's any meaningful data to show
    meaningful_data = {k: v for k, v in data.items() if k != '_id' and v}
    
    if not meaningful_data:
        await update.message.reply_text(
            "📋 You haven't set any preferences yet.\n"
            "Use /health and /diet to set your preferences."
        )
        return
    
    status_text = "📋 *Your Current Preferences:*\n\n"
    
    # Health info
    if any(data.get(key) for key in ['blood_pressure', 'blood_sugar', 'cholesterol']):
        status_text += "🏥 *Health Information:*\n"
        if data.get('blood_pressure'):
            bp_text = bot.health_options['blood_pressure'].get(data['blood_pressure'], data['blood_pressure'])
            status_text += f"• Blood Pressure: {bot.escape_markdown(bp_text)}\n"
        if data.get('blood_sugar'):
            bs_text = bot.health_options['blood_sugar'].get(data['blood_sugar'], data['blood_sugar'])
            status_text += f"• Blood Sugar: {bot.escape_markdown(bs_text)}\n"
        if data.get('cholesterol'):
            chol_text = bot.health_options['cholesterol'].get(data['cholesterol'], data['cholesterol'])
            status_text += f"• Cholesterol: {bot.escape_markdown(chol_text)}\n"
        status_text += "\n"
    
    # Dietary info
    if data.get('dietary_restrictions') or data.get('allergies'):
        status_text += "🌱 *Dietary Information:*\n"
        if data.get('dietary_restrictions'):
            status_text += f"• Restrictions: {bot.escape_markdown(data['dietary_restrictions'])}\n"
        if data.get('allergies'):
            status_text += f"• Allergies: {bot.escape_markdown(data['allergies'])}\n"
    
    try:
        await update.message.reply_text(status_text, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error sending status message: {e}")
        # Fallback without markdown
        plain_text = status_text.replace('*', '').replace('\\', '')
        await update.message.reply_text(plain_text)

async def my_recipes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display a list of the user's saved recipes."""
    user_id = update.effective_user.id
    recipes = get_user_recipes(user_id)

    if not recipes:
        await update.message.reply_text("You have no saved recipes yet. Start creating one by sending me ingredients!")
        return

    keyboard = []
    for recipe in recipes:
        # The recipe name might be long, so we truncate it for the button label.
        recipe_name = recipe['recipe']['name']
        button_text = (recipe_name[:25] + '...') if len(recipe_name) > 28 else recipe_name
        # The callback data will be the MongoDB document's _id as a string.
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"view_recipe_{str(recipe['_id'])}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📚 *Your Saved Recipes:*\n\nSelect a recipe to view its details.", reply_markup=reply_markup, parse_mode='Markdown')


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Ensure user data is loaded before proceeding
    load_user_preferences(user_id)
    
    if data.startswith("health_"):
        if data == "health_bp":
            keyboard = [
                [InlineKeyboardButton("Normal (120/80)", callback_data="bp_normal")],
                [InlineKeyboardButton("Elevated (120-129/80)", callback_data="bp_elevated")],
                [InlineKeyboardButton("High Stage 1", callback_data="bp_high_stage1")],
                [InlineKeyboardButton("High Stage 2", callback_data="bp_high_stage2")],
                [InlineKeyboardButton("Back", callback_data="health_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🩺 Select your blood pressure level:",
                reply_markup=reply_markup
            )
        
        elif data == "health_bs":
            keyboard = [
                [InlineKeyboardButton("Normal (70-100 mg/dL)", callback_data="bs_normal")],
                [InlineKeyboardButton("Prediabetic (100-125 mg/dL)", callback_data="bs_prediabetic")],
                [InlineKeyboardButton("Diabetic (126+ mg/dL)", callback_data="bs_diabetic")],
                [InlineKeyboardButton("Back", callback_data="health_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🩸 Select your blood sugar level:",
                reply_markup=reply_markup
            )
        
        elif data == "health_chol":
            keyboard = [
                [InlineKeyboardButton("Normal (<200 mg/dL)", callback_data="chol_normal")],
                [InlineKeyboardButton("Borderline (200-239 mg/dL)", callback_data="chol_borderline")],
                [InlineKeyboardButton("High (240+ mg/dL)", callback_data="chol_high")],
                [InlineKeyboardButton("Back", callback_data="health_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🫀 Select your cholesterol level:",
                reply_markup=reply_markup
            )
        
        elif data == "health_done":
            await query.edit_message_text("✅ Health information setup complete!")
        
        elif data == "health_back":
            keyboard = [
                [InlineKeyboardButton("Blood Pressure", callback_data="health_bp")],
                [InlineKeyboardButton("Blood Sugar", callback_data="health_bs")],
                [InlineKeyboardButton("Cholesterol", callback_data="health_chol")],
                [InlineKeyboardButton("Done", callback_data="health_done")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🏥 *Health Information Setup*\n\nSelect which health information you'd like to set:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    # Handle health value selections
    elif data.startswith(("bp_", "bs_", "chol_")):
        health_type, value = data.split("_", 1)
        
        if health_type == "bp":
            user_data[user_id]['blood_pressure'] = value
            await query.edit_message_text(f"✅ Blood pressure set to: {bot.health_options['blood_pressure'][value]}")
        elif health_type == "bs":
            user_data[user_id]['blood_sugar'] = value
            await query.edit_message_text(f"✅ Blood sugar set to: {bot.health_options['blood_sugar'][value]}")
        elif health_type == "chol":
            user_data[user_id]['cholesterol'] = value
            await query.edit_message_text(f"✅ Cholesterol set to: {bot.health_options['cholesterol'][value]}")
        
        # Save updated preferences to DB
        save_user_preferences(user_id, user_data[user_id])
    
    # Handle recipe view buttons (from new recipe generation)
    elif data.startswith("recipe_"):
        # The recipe is stored in the cache after generation
        recipe_data = user_data[user_id].get('last_recipe')
        if not recipe_data:
            await query.edit_message_text("❌ No recipe data found. Please create a new recipe.")
            return
        
        try:
            if data == "recipe_main":
                message = bot.format_recipe_message(recipe_data)
                keyboard = [
                    [InlineKeyboardButton("📊 Nutrition", callback_data="recipe_nutrition"),
                     InlineKeyboardButton("🧠 Facts", callback_data="recipe_facts")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='MarkdownV2')
            
            elif data == "recipe_nutrition":
                message = bot.format_nutrition_message(recipe_data)
                keyboard = [
                    [InlineKeyboardButton("🍽️ Recipe", callback_data="recipe_main"),
                     InlineKeyboardButton("🧠 Facts", callback_data="recipe_facts")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='MarkdownV2')
            
            elif data == "recipe_facts":
                message = bot.format_facts_message(recipe_data)
                keyboard = [
                    [InlineKeyboardButton("🍽️ Recipe", callback_data="recipe_main"),
                     InlineKeyboardButton("📊 Nutrition", callback_data="recipe_nutrition")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Error formatting recipe message: {e}")
            # Fallback without markdown
            plain_message = "❌ Error displaying recipe. Please try creating a new recipe."
            await query.edit_message_text(plain_message)
            
    # Handle viewing a saved recipe from /myrecipes
    elif data.startswith("view_recipe_"):
        recipe_id_str = data.replace("view_recipe_", "")
        
        if recipes_collection is None:
            await query.edit_message_text("❌ Database not connected. Cannot retrieve recipe.")
            return
            
        try:
            recipe_data = recipes_collection.find_one({'_id': ObjectId(recipe_id_str)})
            if not recipe_data:
                await query.edit_message_text("❌ Recipe not found. It might have been deleted.")
                return

            # Store it in the cache so the Nutrition/Facts buttons work
            user_data[user_id]['last_recipe'] = recipe_data
            
            # Format and send the message
            message = bot.format_recipe_message(recipe_data)
            keyboard = [
                [InlineKeyboardButton("📊 Nutrition", callback_data="recipe_nutrition"),
                 InlineKeyboardButton("🧠 Facts", callback_data="recipe_facts")],
                [InlineKeyboardButton("🗑️ Delete Recipe", callback_data=f"delete_recipe_{recipe_id_str}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='MarkdownV2')

        except Exception as e:
            logger.error(f"Error retrieving recipe {recipe_id_str}: {e}")
            await query.edit_message_text("❌ An error occurred while fetching the recipe.")

    # Handle saving the last generated recipe
    elif data == "save_last_recipe":
        recipe_data = user_data[user_id].get('last_recipe')
        if not recipe_data:
            await query.answer("Error: Couldn't find the recipe to save.", show_alert=True)
            return

        save_recipe(user_id, recipe_data)
        await query.answer("Recipe saved successfully!", show_alert=True)

        # Rebuild keyboard without the save button to prevent duplicates
        new_keyboard = [
            [
                InlineKeyboardButton("📊 Nutrition", callback_data="recipe_nutrition"),
                InlineKeyboardButton("🧠 Facts", callback_data="recipe_facts")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(new_keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)

    # Handle deleting a recipe
    elif data.startswith("delete_recipe_"):
        recipe_id_str = data.replace("delete_recipe_", "")
        
        success = delete_recipe(recipe_id_str)

        if success:
            await query.edit_message_text("🗑️ Recipe successfully deleted.")
        else:
            await query.answer("Error: Could not delete the recipe.", show_alert=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages for setting preferences or generating recipes."""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Ensure user data is loaded for the session
    load_user_preferences(user_id)
    
    # Check if user is in the process of setting preferences
    if user_data[user_id].get('setting'):
        setting_type = user_data[user_id]['setting']
        
        if setting_type == 'dietary_restrictions':
            user_data[user_id]['dietary_restrictions'] = message_text if message_text.lower() != 'none' else ''
            user_data[user_id]['setting'] = 'allergies'
            
            await update.message.reply_text(
                "Great! Now please send me your allergies (e.g., nuts, dairy, shellfish, eggs)\n"
                "Or type 'none' if you don't have any allergies."
            )
            return
        
        elif setting_type == 'allergies':
            user_data[user_id]['allergies'] = message_text if message_text.lower() != 'none' else ''
            del user_data[user_id]['setting']
            
            # Save all preferences to DB after the setup flow is complete
            save_user_preferences(user_id, user_data[user_id])
            
            await update.message.reply_text(
                "✅ Dietary preferences saved!\n"
                "Now you can send me ingredients or describe what you want to cook!"
            )
            return
    
    # If not setting preferences, assume the message is for recipe generation
    loading_message = random.choice(LOADING_MESSAGES)
    await update.message.reply_text(loading_message)
    
    try:
        # Get user preferences from the cache
        prefs = user_data.get(user_id, {})
        health_stats = {
            'blood_pressure': prefs.get('blood_pressure', ''),
            'blood_sugar': prefs.get('blood_sugar', ''),
            'cholesterol': prefs.get('cholesterol', '')
        }
        dietary_restrictions = prefs.get('dietary_restrictions', '')
        allergies = prefs.get('allergies', '')
        
        # Create prompt and generate recipe
        prompt = bot.create_recipe_prompt(message_text, health_stats, dietary_restrictions, allergies)
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse JSON response
        try:
            recipe_data = json.loads(response_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                recipe_data = json.loads(json_match.group())
            else:
                raise Exception("Failed to parse recipe data from AI response.")
        
        # Store recipe in cache for button navigation
        user_data[user_id]['last_recipe'] = recipe_data
        
        # Format and send recipe
        recipe_message = bot.format_recipe_message(recipe_data)
        
        keyboard = [
            [InlineKeyboardButton("💾 Save Recipe", callback_data="save_last_recipe")],
            [InlineKeyboardButton("📊 Nutrition", callback_data="recipe_nutrition"),
             InlineKeyboardButton("🧠 Facts", callback_data="recipe_facts")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await update.message.reply_text(
                recipe_message,
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Error sending recipe with markdown: {e}")
            plain_message = recipe_message.replace('*', '').replace('\\', '')
            await update.message.reply_text(
                plain_message,
                reply_markup=reply_markup
            )
        
    except Exception as e:
        logger.error(f"Error generating recipe: {e}")
        await update.message.reply_text(
            "❌ Sorry, I couldn't generate a recipe right now. Please try again with different ingredients or check if your message is clear."
        )

def main():
    """Run the bot"""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("diet", diet_command))
    application.add_handler(CommandHandler("myrecipes", my_recipes_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run the bot
    print("🤖 Sous-Chef AI Telegram Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
