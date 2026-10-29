from libraries import *
from util import *
import os
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import telebot.apihelper as apihelper

bot = telebot.TeleBot(config.token)

# The route to api.telegram.org here drops the first connect and takes ~3s to warm up.
# Retry inside the API layer so a single failed connect is not a dropped update.
apihelper.RETRY_ON_ERROR = True
apihelper.MAX_RETRIES = int(os.environ.get('MJ_MAX_RETRIES', 4))
apihelper.RETRY_TIMEOUT = 2

server = Flask(__name__)
win = {}
typz = {}
games = {}
chatStatus = {}
maxtai = 5


#-----------------------checks--------------------------------
def check1(s, message):
    typ = []    
    buttons = []
    for i in range(1,s.maxtai+1,1):
        typ.append(str(i) + ' Tai')
    typ.append("Kang")
    typ.append("Kang 暗")
    typ.append(u'\U0001F408')
    typ.append(u'\U0001F408'+" 暗")
    typ.append(u'\U0001F940')
    typ.append(u'\U0001F940'+" 暗")

    for entry in typ:
        buttons = buttons + ["東 " + entry, "南 " + entry, "西 " + entry, "北 " + entry]
    buttons = buttons + ["Manual Edits", "Remove Last", "/end"]
    return (message in buttons)

def check2(chastus, message):
    buttons = ["東", "南", "西", "北", "zimo", "Back"]
    #these entries only have continue/back
    if chastus in ['東 🐈', '南 🐈', '西 🐈', '北 🐈', '東 🐈 暗', '南 🐈 暗', '西 🐈 暗', '北 🐈 暗', '東 🥀 暗', '南 🥀 暗', '西 🥀 暗', '北 🥀 暗', '東 Kang 暗', '南 Kang 暗', '西 Kang 暗', '北 Kang 暗']: 
        buttons = ["Continue", "Back"]
    #remove the winner's button
    elif len(chastus.split()) > 0: 
        ori = chastus.split()[0]
        buttons.remove(ori)
    
    return (message in buttons)

def check3(message):
    buttons = ['Pay Rate', 'Shooter', 'Max Tai', '/play' ,'Back']
    return (message in buttons)

#-----------------------Reply Markups---------------------------------
def start_markup():
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True, one_time_keyboard=True)
    markup.add('/start', '/play', '/end', '/settings')
    markup.row = 1
    return markup

def settings_markup():
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True, one_time_keyboard=True)
    markup.add('Pay Rate', 'Shooter', 'Max Tai', '/play', 'Back')
    return markup

def play_markup(s):
    markup = types.ReplyKeyboardMarkup(row_width=4, resize_keyboard=True, one_time_keyboard=True)
    typ = []
    for i in range(1,s.maxtai+1,1):
        typ.append(str(i) + ' Tai')

    typ.append("Kang")
    typ.append("Kang 暗")
    typ.append(u'\U0001F408')
    typ.append(u'\U0001F408'+" 暗")
    typ.append(u'\U0001F940')
    typ.append(u'\U0001F940'+" 暗")
    #kang flower

    for entry in typ:
        markup.add("東 " + entry, "南 " + entry, "西 " + entry, "北 " + entry)
    markup.add("Manual Edits", "Remove Last", "/end")
    return markup

def play_2_markup(x):
    markup = types.ReplyKeyboardMarkup(row_width=4, resize_keyboard=True, one_time_keyboard=True)
    if x == "東":
        markup.add("zimo", "南", "西", "北", "Back")
    if x == "南":
        markup.add("東", "zimo", "西", "北",  "Back")
    if x == "西":
        markup.add("東", "南", "zimo", "北", "Back")
    if x == "北":
        markup.add("東", "南", "西", "zimo", "Back")
    return markup

def play_3_markup():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
    markup.add("Continue", "Back")
    return markup

def start_msg(message):
    bot.send_message(message.chat.id, 
    "Hello " + u'\U000026C4' + " This is a Mahjong Calculator!\n\n" + 
    "Default Settings:\n" +
    "*Pay Rate: *" + str(games[str(message.chat.id)].rate) + "\n" + 
    "*Shooter Pay: *" + str(games[str(message.chat.id)].shooter) + "\n"+
    "*Maximum Tai: *" + str(games[str(message.chat.id)].maxtai) + "\n" +
    "*Player Names: *" + str(games[str(message.chat.id)].players) + "\n" +
    "*Starting Money: *" + str(games[str(message.chat.id)].banks) + "\n",
    parse_mode= 'Markdown')
    bot.send_message(message.chat.id, 
    "*Supported Commands:*\n"
    "/start: Restart the Bot \n" + 
    "/play: Play the Game \n"+
    "/end: End the Game (and count money) \n" +
    "/settings: Manage Settings \n", 
    parse_mode= 'Markdown', reply_markup=start_markup())

#-----------------------Bot Commands---------------------------------

@bot.message_handler(commands=['start', 'help', 'reset'])
def start(message):
    games[str(message.chat.id)] = session() #initilaize a session
    start_msg(message)

@bot.message_handler(commands=['settings'])
def settings(message):
    bot.send_message(message.chat.id, "Change Settings?", parse_mode= 'Markdown', reply_markup=settings_markup())
    chatStatus[str(message.chat.id)] = 'waiting_for_settings'

@bot.message_handler(commands=['play'])
def startgame(message):
    bot.send_message(message.chat.id, 
    games[str(message.chat.id)].ompm(), 
    parse_mode= 'Markdown', reply_markup=play_markup(games[str(message.chat.id)]))
    chatStatus[str(message.chat.id)] = 'waiting_for_feeder'

@bot.message_handler(commands=['end'])
def endgame(message):
    #diplay difference
    bot.send_message(message.chat.id, 
    games[str(message.chat.id)].howtopay(), parse_mode= 'Markdown')
    chatStatus[str(message.chat.id)] = 'End'
    
pd = {"東":1, "南":2, "西":3, "北":4, "zimo": "zimo"}



def endofplay(message):
    bot.send_message(message.chat.id, games[str(message.chat.id)].ompm(), parse_mode= 'Markdown', reply_markup=play_markup(games[str(message.chat.id)]))
    chatStatus[str(message.chat.id)] = 'waiting_for_feeder'

def endofsettings(message):
    bot.send_message(message.chat.id, 
    "Default Settings:\n" +
    "*Pay Rate: *" + str(games[str(message.chat.id)].rate) + "\n" + 
    "*Shooter Pay: *" + str(games[str(message.chat.id)].shooter) + "\n"+
    "*Maximum Tai: *" + str(games[str(message.chat.id)].maxtai) + "\n" +
    "*Player Names: *" + str(games[str(message.chat.id)].players) + "\n" +
    "*Starting Money: *" + str(games[str(message.chat.id)].banks) + "\n",
    parse_mode= 'Markdown', reply_markup=settings_markup())
    chatStatus[str(message.chat.id)] = 'waiting_for_settings'

@bot.message_handler()
def responses(message):
    if str(message.chat.id) in chatStatus:

        ##------------(a) Settings COMMAND-------------------
        if chatStatus[str(message.chat.id)] == 'waiting_for_settings':
            chatStatus[str(message.chat.id)] = message.text
            #('Pay Rate', 'Shooter', 'Max Tai', 'Starting Money')
            if check3(message.text) == False:
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown', reply_markup=settings_markup())
                chatStatus[str(message.chat.id)] = 'waiting_for_settings'
            elif message.text == 'Pay Rate': # accept response
                markup = types.ReplyKeyboardMarkup(row_width=4, resize_keyboard=True, one_time_keyboard=True)
                markup.add('0.1', '0.2', '0.3', '1')
                bot.reply_to(message, '$ (n)', parse_mode= 'Markdown', reply_markup=markup)
            elif message.text == 'Shooter': # accept response
                markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
                markup.add("True", "False")
                bot.reply_to(message, 'True / False', parse_mode= 'Markdown', reply_markup=markup)
            elif message.text == 'Max Tai': # accept response
                markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True, one_time_keyboard=True)
                markup.add('5 Tai', '6 Tai', '7 Tai', '8 Tai', '9 Tai', '10 Tai')
                bot.reply_to(message, '(n) Tai', parse_mode= 'Markdown', reply_markup=markup)
            elif message.text == "Back":
                start_msg(message)
        
        ##------------(b) Settings COMMAND-------------------
        elif chatStatus[str(message.chat.id)] == "Pay Rate": 
            if len(message.text.split()) != 1 or message.text.replace(".", "").isdigit() == False: #invalid cases
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown', reply_markup=settings_markup())
            elif message.text == "Back":
                endofsettings(message) 
            else:
                games[str(message.chat.id)].definesettings(rate = message.text)
                endofsettings(message)

        elif chatStatus[str(message.chat.id)] == "Shooter": 
            if len(message.text.split()) != 1 or message.text in ["True","False"] == False: #invalid cases
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown', reply_markup=settings_markup())
            elif message.text == "Back":
                endofsettings(message) 
            else:
                if message.text == "True":
                    games[str(message.chat.id)].definesettings(shooter = True)
                elif message.text == "False":
                    games[str(message.chat.id)].definesettings(shooter = False)
                endofsettings(message)

        elif chatStatus[str(message.chat.id)] == "Max Tai": 
            if message.text.split()[0].isdigit() == False : #invalid cases
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown', reply_markup=settings_markup())
            elif "." in message.text: #have decimals
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown', reply_markup=settings_markup())
            elif float(message.text.split()[0]) >= 11: #max tai too high
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown', reply_markup=settings_markup())
            elif message.text == "Back":
                endofsettings(message) 
            else:
                games[str(message.chat.id)].definesettings(maxtai = int(message.text.split()[0]))
                endofsettings(message)
        


        ##------------(a) PLAY COMMAND (Winner/Type Layer)-------------------

        elif chatStatus[str(message.chat.id)] == 'waiting_for_feeder':
            chatStatus[str(message.chat.id)] = message.text

            #check anomalies
            if check1(games[str(message.chat.id)], message.text) == False:
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown', reply_markup=play_markup(games[str(message.chat.id)]))
                chatStatus[str(message.chat.id)] = 'waiting_for_feeder'

            elif message.text == "Manual Edits":
                bot.reply_to(message, '..1 ..2 ..3 ..4', parse_mode= 'Markdown')
            elif message.text == "Remove Last":
                bot.reply_to(message, '...?', parse_mode= 'Markdown', reply_markup=play_3_markup())

             #special cases
            elif len(message.text.split()) == 2 and message.text.split()[1] == u'\U0001F408': #animal (non an)
                bot.reply_to(message, '...?', parse_mode= 'Markdown', reply_markup=play_3_markup())
            elif len(message.text.split()) == 3 and message.text.split()[2] == "暗": #special cases
                bot.reply_to(message, '...?', parse_mode= 'Markdown', reply_markup=play_3_markup())
                
            else: # should check if all response
                bot.reply_to(message, 'Who fed?', parse_mode= 'Markdown', reply_markup=play_2_markup(message.text.split()[0]))
            
        ##------------(b) PLAY COMMAND (Loser Layer)-------------------

        elif len(chatStatus[str(message.chat.id)].split()) > 1 and chatStatus[str(message.chat.id)].split()[1].isnumeric(): # tai win
            winner = chatStatus[str(message.chat.id)].split()[0]
            if check2(chatStatus[str(message.chat.id)], message.text) == False:
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown')
                endofplay(message) 
            elif message.text == "Back":
                endofplay(message) 
            else:
                tai = chatStatus[str(message.chat.id)].split()[1]
                loser = message.text
                games[str(message.chat.id)].pay(ntai = int(tai), player_win = pd[winner], player_lose = pd[loser])
                endofplay(message)

        elif len(chatStatus[str(message.chat.id)].split()) > 1 and chatStatus[str(message.chat.id)].split()[1] == "Kang": # kang
            winner = chatStatus[str(message.chat.id)].split()[0]
            if check2(chatStatus[str(message.chat.id)], message.text) == False:
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown')
                endofplay(message) 
            elif message.text == "Back":
                endofplay(message) 
            elif len(chatStatus[str(message.chat.id)].split()) == 3: # an
                games[str(message.chat.id)].pay_kang(p_win = pd[winner], p_lose = "zimo", blind = True)
                endofplay(message)        
            else:
                loser = message.text
                games[str(message.chat.id)].pay_kang(p_win = pd[winner], p_lose = pd[loser], blind = False)
                endofplay(message)     
        
        elif len(chatStatus[str(message.chat.id)].split()) > 1 and chatStatus[str(message.chat.id)].split()[1] == u'\U0001F408': #animal
            winner = chatStatus[str(message.chat.id)].split()[0]
            if check2(chatStatus[str(message.chat.id)], message.text) == False:
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown')
                endofplay(message) 
            elif message.text == "Back":
                endofplay(message) 
            elif len(chatStatus[str(message.chat.id)].split()) == 3: # an
                games[str(message.chat.id)].pay_flower(p_win = pd[winner], p_lose = "zimo", blind= True) 
                endofplay(message)  
            else:
                games[str(message.chat.id)].pay_flower(p_win = pd[winner], p_lose = "zimo", blind= False)  
                endofplay(message) 
        
        elif len(chatStatus[str(message.chat.id)].split()) > 1 and chatStatus[str(message.chat.id)].split()[1] == u'\U0001F940': #flower
            winner = chatStatus[str(message.chat.id)].split()[0]
            if check2(chatStatus[str(message.chat.id)], message.text) == False:
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown')
                endofplay(message) 
            elif message.text == "Back":
                endofplay(message) 
            elif len(chatStatus[str(message.chat.id)].split()) == 3: # an
                games[str(message.chat.id)].pay_flower(p_win = pd[winner], p_lose = "zimo", blind= True)  
                endofplay(message) 
            else:
                games[str(message.chat.id)].pay_flower(p_win = pd[winner], p_lose = pd[message.text], blind= False) 
                endofplay(message)
        
        elif len(chatStatus[str(message.chat.id)].split()) > 1 and chatStatus[str(message.chat.id)].split()[1] == "Edits":
            if len(message.text.split()) == 4 and message.text.replace(" ", "").replace(".", "").replace("-", "").isdigit():
                mts = message.text.split()
                if abs(float(mts[0]) + float(mts[1]) + float(mts[2]) + float(mts[3])) > 0.1 :
                    bot.reply_to(message, 'Invalid Entry, Entries must be zero sum', parse_mode= 'Markdown')
                    endofplay(message)
                else:
                    games[str(message.chat.id)].manual(float(mts[0]),float(mts[1]),float(mts[2]),float(mts[3]))
                    endofplay(message)
            else:
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown')
                endofplay(message)

        elif len(chatStatus[str(message.chat.id)].split()) > 1 and chatStatus[str(message.chat.id)].split()[1] == "Last": #Remove Last
            if message.text == "Back":
                endofplay(message) 
            elif message.text == "Continue":
                games[str(message.chat.id)].redolast()
                endofplay(message) 
            else:
                bot.reply_to(message, 'Invalid Entry', parse_mode= 'Markdown')
                endofplay(message) 
        
        ##------------END COMMAND-------------------
        elif chatStatus[str(message.chat.id)] == "End":
            return


#bot.polling()

#--------------Webhook

@server.route('/' + config.token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200


@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=config.webhook_url + config.token)
    return "!", 200


if __name__ == "__main__":
    if os.environ.get('MJ_MODE', 'polling') == 'webhook':
        server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
    else:
        # Local development: polling needs no public HTTPS URL.
        #
        # MJ_POLL_TIMEOUT is the getUpdates hold time. telebot sends it as the API
        # 'timeout' param. Keep it low: some networks drop long-held connections,
        # and telebot 4.5.1 lets a ReadTimeout escape polling() and kill the process.
        poll_timeout = int(os.environ.get('MJ_POLL_TIMEOUT', 5))
        print('Bot online (polling, hold=%ss). Press Ctrl+C to stop.' % poll_timeout)
        while True:
            try:
                bot.polling(none_stop=True, interval=1, skip_pending=False,
                            long_polling_timeout=poll_timeout)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                # Transient drop (ReadTimeout/ConnectionError): restart, don't die.
                print('Polling dropped (%s: %s) - restarting in 3s' % (type(e).__name__, e))
                time.sleep(3)