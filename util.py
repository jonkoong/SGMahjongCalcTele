#from base64 import urlsafe_b64decode
import json
from libraries import *

#    payment -10/20, 20/40
#    shooter pay?
#    maximum Tai

# Payout multiplier per tai index (0..10), doubling each tai.
TAI_LADDER = [0, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]


class session:
    def __init__(self):
        self.players = ["東","南","西","北"]
        #starting money
        self.banks = [0,0,0,0]
        #settings
        self.rate = float(0.1)
        self.shooter = True
        self.maxtai = 5
        self.last = [np.array([0,0,0,0])]
    
    def defineplayernames(self, name1, name2, name3, name4):
        self.players = [name1, name2, name3, name4]

    def definesettings(self, rate = 0.1, shooter = True, maxtai = 5):
        self.rate = float(rate)
        self.shooter = shooter
        self.maxtai = maxtai
        #self.kang = kang

    def pay(self, ntai, player_win, player_lose = "zimo"):
        if self.shooter == True:  
            self.shooterpay(ntai, player_win, player_lose)
        elif self.shooter == False:
            self.nshooterpay(ntai, player_win, player_lose)

    def shooterpay(self, ntai, player_win, player_lose):
        #mark the losses
        factor = np.array([0,0,0,0])
        if player_lose == "zimo":
            factor = np.array([-0.5,-0.5,-0.5,-0.5])
            factor[player_win-1] = 1.5
        else: #mark the guy that loses
            factor[player_win-1] = 1
            factor[player_lose-1] = -1

        #calculate losses
        x = np.array(TAI_LADDER)
        p = self.rate*x

        #pay off losses
        self.banks = self.banks +  p[ntai]*factor
        self.last.append(p[ntai]*factor)
    
    def nshooterpay(self, ntai, player_win, player_lose):
        #mark the losses
        factor = np.array([0,0,0,0])
        if player_lose == "zimo":
            factor = np.array([-0.5,-0.5,-0.5,-0.5])
            factor[player_win-1] = 1.5
        else: #mark the guy that loses
            factor = np.array([-0.25,-0.25,-0.25,-0.25])
            factor[player_win-1] = 1
            factor[player_lose-1] = -0.5

        #calculate losses
        x = np.array(TAI_LADDER)
        p = self.rate*x

        #pay off losses
        self.banks = self.banks +  p[ntai]*factor
        self.last.append(p[ntai]*factor)

    def pay_kang(self, p_win, p_lose, blind):
        factor = np.array([0,0,0,0])

        if self.shooter == True:

            if blind == False and p_lose != "zimo": 
                factor[p_win-1] = 3
                factor[p_lose-1] = -3
            elif blind == False and p_lose == "zimo": 
                factor = np.array([-1,-1,-1,-1])
                factor[p_win-1] = 3
            elif blind == True and p_lose != "zimo": 
                return #doesnt exist
            elif blind == True and p_lose == "zimo": 
                factor = np.array([-2,-2,-2,-2])
                factor[p_win-1] = 6

        elif self.shooter == False: ##CHANGE

            if blind == False and p_lose != "zimo": #player shoot
                factor = np.array([-1,-1,-1,-1])
                factor[p_win-1] = 3
            elif blind == False and p_lose == "zimo": 
                factor = np.array([-2,-2,-2,-2])
                factor[p_win-1] = 6
            elif blind == True and p_lose != "zimo": 
                return #doesnt exist
            elif blind == True and p_lose == "zimo": 
                factor = np.array([-4,-4,-4,-4])
                factor[p_win-1] = 12

        #pay off losses
        self.banks = self.banks + factor*self.rate
        self.last.append(factor*self.rate)

    #flower...!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    def pay_flower(self, p_win, p_lose, blind):
        factor = np.array([0,0,0,0])
        if self.shooter == True:
            if blind == False and p_lose != "zimo": 
                factor[p_win-1] = 1
                factor[p_lose-1] = -1
            elif blind == False and p_lose == "zimo": 
                factor = np.array([-1,-1,-1,-1])
                factor[p_win-1] = 3
            elif blind == True and p_lose == "zimo": 
                factor = np.array([-2,-2,-2,-2])
                factor[p_win-1] = 6
            
        elif self.shooter == False: ##CHANGE
            if blind == False and p_lose != "zimo": #cant yao others
                return
            elif blind == False and p_lose == "zimo": # yao ziji
                factor = np.array([-1,-1,-1,-1])
                factor[p_win-1] = 3
            elif blind == True and p_lose == "zimo": # an yao
                factor = np.array([-2,-2,-2,-2])
                factor[p_win-1] = 6
            
        #pay off losses
        self.banks = self.banks + factor*self.rate
        self.last.append(factor*self.rate)

    def manual(self, p1, p2, p3, p4):
        self.banks = self.banks + np.array([p1,p2,p3,p4])
        self.last.append(np.array([p1,p2,p3,p4]))

    def redolast(self):
        if self.last != []:
            self.banks = self.banks - self.last[-1]
            self.last.pop()
        else:
            return

    def ompm(self):
        text = ""
        for i, player in enumerate(self.players) :
            text = text + str(player) + "'s total: $" + "%.2f" % self.banks[i] + '\n'
        return text

    def howtopay(self): #[4, -1, 5,-3]
        paydict = dict(zip(self.players, self.banks))
        paydict = {k: v for k, v in paydict.items() if v != 0}
        #print (paydict)
        text = ""
        if len(paydict) == 0: #no payment
            text = "No Payment"
        elif len([x for x in self.banks if x < 0]) == 1: #1 loser in 4, 1 loser in 3
            payer = self.players[next(x[0] for x in enumerate(self.banks) if x[1] < 0)] #find payer negative
            for key, value in paydict.items():
                if value > 0:
                    text = text + str(payer) + " pays " + str(key) + ": $" + "%.2f" % abs(value) + "\n"
        elif len([x for x in self.banks if x < 0]) == 2 and len(paydict) == 4 : #2 losers 
            pd = dict(sorted(paydict.items(), key=lambda item: item[1], reverse = True)) #[4,3,-1,-6]
            if abs(list(pd.values())[3]) >=  abs(list(pd.values())[0]): #biggest lose >= win #[4,3,-1,-6]
                #biggest loser settle first
                text = text + list(pd.keys())[3] + " pays " + list(pd.keys())[0] + ": $" + "%.2f" % list(pd.values())[0] + "\n" #pay win directly completely
                leftover = abs(list(pd.values())[3]) - abs(list(pd.values())[0]) 
                if leftover != 0: 
                    text = text + list(pd.keys())[3] + " pays " + list(pd.keys())[1] + ": $" + "%.2f" % leftover + "\n" #pay leftovers to 2nd winner
                text = text + list(pd.keys())[2] + " pays " + list(pd.keys())[1] + ": $" + "%.2f" % abs(list(pd.values())[2]) + "\n" #pay leftovers to 2nd winner
            elif abs(list(pd.values())[0]) >  abs(list(pd.values())[3]): #biggest win >= lose #[6,3,-4,-5]
                #biggest loser settle first
                text = text + list(pd.keys())[3] + " pays " + list(pd.keys())[0] + ": $" + "%.2f" % abs(list(pd.values())[3]) + "\n" #pay win
                leftover = abs(list(pd.values())[0]) -  abs(list(pd.values())[3])
                text = text + list(pd.keys())[2] + " pays " + list(pd.keys())[0] + ": $" + "%.2f" % leftover + "\n" #pay leftovers to 2nd winner
                text = text + list(pd.keys())[2] + " pays " + list(pd.keys())[1] + ": $" + "%.2f" % list(pd.values())[1] + "\n" #pay leftovers to 2nd winner
        elif len([x for x in self.banks if x < 0]) == len(paydict)-1: #3 loser in 4, 2 loser in 3
            payee = self.players[next(x[0] for x in enumerate(self.banks) if x[1] > 0)] #find payee positive
            for key, value in paydict.items():
                if value < 0:
                    text = text + str(key) + " pays " + str(payee) + ": $" + "%.2f" % abs(value) + "\n"
        return text


#s = session()
#s.manual(1,2,3,4)
#print(s.ompm())
#s.defineplayernames("x1", "x2", "x3", "x4")
#s.definesettings(rate = 0.1, shooter = False, maxtai = 5)
#s.pay(ntai = 4, player_win = 1, player_lose = 4)
#s.pay(ntai = 3, player_win = 2, player_lose = 4)
#s.pay(ntai = 1, player_win = 4, player_lose = 3)
#s.pay(ntai = 5, player_win = 2, player_lose = "zimo")
#print(s.ompm())
#print(s.howtopay())

#s.ompm()
#s.pay_kang(p_win = 1, p_lose = 'zimo', blind= False)
#s.ompm()