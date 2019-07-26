import random
from datetime import datetime, timezone, timedelta
import time
import re
import requests
import json
import os
import logging
import urllib
from util import load_json

FULL_MODE = True
try:
    import BookingHelper
    import InfoHelper
except:
    FULL_MODE = False


class Bot:
    # settings
    SETTINGS = load_json('settings.json')
    REPLY = load_json('reply.json')
    TRASHES = load_json('trash.json')
    NEW_TRASHES = load_json('new_trash.json')
    COURSES = load_json("course.json")
    FIXED_REPLY_DICT = REPLY['FIXED_REPLY_DICT']
    REG_REPLY_DICT = REPLY['REG_REPLY_DICT']

    def getWord(self):
        self.switch()
        if self.running:
            processes = [
                self.replyAT, self.replyFunction, self.checkMeme, self.study,
                self.replyStudy, self.checkXM, self.checkKeywords,
                self.followRepeat, self.rndRepeat, self.rndXM
            ]
            for process in processes:
                process()
                if self.res:
                    break

    def getReply(self, key):
        re = Bot.REPLY.get(key)
        return random.choice(re) if re else ''

    # switch on / off of the bot
    def switch(self):
        if len(self.msg) > 5:
            return
        user_id = self.context['user_id']
        if (re.search(r'关|停|锤|砸|闭嘴', self.msg) and re.search(r'复读机', self.msg))\
                and not re.search(r'已经|不|开', self.msg):
            if self.running:
                t = datetime.now(timezone(timedelta(hours=8)))
                if user_id % (t.month * 100 + t.day) % 100 < Bot.SETTINGS['CLOSE_PR'] * 100 or \
                   user_id in Bot.SETTINGS['ADMIN'] or \
                   user_id in Bot.SETTINGS['ALLOWED_LIST'] and \
                   user_id not in Bot.SETTINGS['DISALLOWED_LIST']:
                    self.running = False
                    self.res = self.getReply('switch_off_successful')
                else:
                    self.res = self.getReply('switch_off_failed')
        elif (re.search(r'开|启动|修', self.msg) and re.search(r'复读机', self.msg))\
                and not re.search(r'已经|不要', self.msg):
            if not self.running:
                myrand = random.random()
                if myrand < Bot.SETTINGS['OPEN_FAILED_PR']:
                    self.res = self.getReply('switch_on_failed')
                else:
                    self.running = True
                    self.res = self.getReply('switch_on_successful')
            else:
                self.res = self.getReply('switch_on_already')

    # special reply for message starting with '#'
    def replyFunction(self):
        if not re.search(r'^#', self.msg):
            return
        tmp_reg = re.search(r'扔(.*)', self.msg)
        if tmp_reg:
            res = self.getThrow(tmp_reg.group(1))
            self.res = res if res else self.getReply('throw_failed')
            return
        tmp_reg = re.search(r'^#(\d{3})是什么', self.msg)
        if tmp_reg:
            res = self.getCourseInfo(tmp_reg.group(1))
            self.res = res if res else self.getReply("course_failed")
            return
        if self.context['group_id'] not in Bot.SETTINGS['ADMIN_GROUP'] and \
            self.context['user_id'] not in Bot.SETTINGS['ADMIN'] or \
            not FULL_MODE:
            return
        if re.search(r'色图', self.msg):
            if self.context['user_id'] not in Bot.SETTINGS['ADMIN']:
                return
            imgUrl = self.getMySetu() if re.search(
                r'我的', self.msg) else self.getSetu()
            if imgUrl:
                self.res = imgUrl
            else:
                self.res = self.getReply('get_image_failed')
            return
        tmp_reg = re.search(r'谁是(.+)|(.+)是谁', self.msg)
        if tmp_reg:
            string = tmp_reg.group(1) if tmp_reg.group(1) else tmp_reg.group(2)
            res = self.ih.getInfo(py=string)
            if res:
                self.res = " ".join(res)
            else:
                self.res = self.getReply('info_failed')
        if re.search(r'开房', self.msg):
            res = self.bh.getSchedule()
            if res:
                self.res = res
            else:
                self.res = self.getReply('book_failed')
        tmp_reg = re.search(r'#查(.+)', self.msg)
        if tmp_reg:
            string = tmp_reg.group(1)
            res = self.ih.getInfo(name=string)
            if res:
                self.res = json.dumps(res, ensure_ascii=False)
            else:
                self.res = self.getReply('info_failed')

    def getThrow(self, keyword):
        if string in ['骰子', '色子']:
            self.res = str(random.randint(1, 6))
        elif string in ['硬币']:
            coin_re = ['正', '反']
            self.res = coin_re[random.randint(0, 1)]
        elif '复读' in string or 'bot' in string:
            self.res = self.getReply('throw_bot')
            if not self.res:
                self.res = f'#扔[CQ:at,qq={self.context["user_id"]}]'
        elif not string:
            self.res = self.getReply('throw_nothing')
        else:
            tmp_re = Bot.TRASHES.get(string)
            if tmp_re is not None:
                self.res = f'{string}：{tmp_re}\n'
            tmp_dict = dict()
            for key, value in Bot.NEW_TRASHES.items():
                if string.lower() in key.lower():
                    tmp_dict[key] = value
            for key, value in sorted(tmp_dict.items(),
                                     key=lambda d: len(d[0])):
                self.res = f'{self.res}{key}：{value}\n'
            self.res = self.res.strip('\n')

    def getCourseInfo(self, keyword):
        re = dict()
        keyword = str(keyword)
        for item in Bot.COURSES:
            courseCode = item['courseCode']
            if keyword in courseCode:
                if re.get(courseCode) is None:
                    re[courseCode] = item.copy()
                    re[courseCode]['termName'] = [re[courseCode]['termName']]
                else:
                    re[courseCode]['termName'].append(item['termName'])
        res = ''
        for item in re.values():
            res += "课程代码:{}\n".format(item['courseCode'])
            res += "课程名称:{} {}\n".format(item['courseName'],
                                         item['courseNameEn'])
            res += "学分:{}\n".format(item['credit'])
            res += "开设时间:"
            for term in set(item['termName']):
                res += "{} ".format(term)
            res += "\n\n"
        return res.strip()

    def getSetu(self):
        url = "https://yande.re/post.json?limit=1&" + \
            f"tags=uncensored&page={random.randint(1, 1000)}"
        try:
            json = requests.get(url).json()
            return json[0]['file_url']
            # querystring = {
            #     "url": json[0]['file_url'],
            #     "key":
            #     "5d22c090b1a9c70e343cfcbf@10b067e933e010e73a0de35e6b59307f"
            # }
            # url = "http://suo.im/api.php"
            # return requests.request("GET", url, params=querystring).text
        except:
            pass

    def getMySetu(self):
        url = "http://59.78.35.49:5000/"
        return requests.request("GET", url).text

    # reply call
    def replyAT(self):
        if (re.search(r'\[CQ:at,qq={}\]'.format(self.context['self_id']),
                      self.msg)):
            self.res = random.choice(Bot.FIXED_REPLY_DICT['AT'])

    # check XM
    def checkXM(self):
        if re.search(r'^xm|^羡慕', self.msg):
            myrand = random.random()
            if myrand <= Bot.SETTINGS['XM_PR']:
                if '呸，老子才不羡慕' + re.sub(r'^xm|^羡慕', '',
                                       self.msg) not in self.selfArr:
                    self.res = self.msg
            elif myrand >= 1 - Bot.SETTINGS['NOT_XM_PR']:  # 避免循环羡慕
                if self.msg not in self.selfArr \
                        and '呸，老子才不羡慕' + re.sub(r'^xm|^羡慕', '', self.msg) not in self.selfArr:
                    self.res = '呸，老子才不羡慕' + re.sub(r'^xm|^羡慕', '', self.msg)

    # check keywords
    def checkKeywords(self):
        if re.search(r'tql|nb|ydl|ddw', self.msg):
            if random.random() <= Bot.SETTINGS['KW_REPEAT_PR']:
                self.res = self.msg

    # check meme & regex replys
    def checkMeme(self):
        for regex, words in Bot.REG_REPLY_DICT.items():
            if re.search(regex, self.msg):
                self.res = random.choice(words)

    # followd repeat
    def followRepeat(self):
        if self.mbrArr.count(self.msg) >= 2:
            self.mbrArr = [''] * 10
            self.res = self.msg
        else:
            self.recordMbrMsg()

    # record previous messages
    def recordMbrMsg(self):
        self.mbrArr[self.mbrIndex] = self.msg
        self.mbrIndex = 0 if self.mbrIndex == 9 else self.mbrIndex + 1
        self.lastMsgInvl += 1
        return

    # random repeat
    def rndRepeat(self):
        if self.lastMsgInvl > Bot.SETTINGS['MIN_MSG_INVL'] and len(
                self.msg) <= Bot.SETTINGS['MAX_RND_RE_LEN']:
            myrand = random.random()
            if (myrand <= Bot.SETTINGS['RND_REPEAT_PR']):
                self.lastMsgInvl = 0
                self.res = self.msg

    # random XM
    def rndXM(self):
        if len(self.msg) > 2 and not re.search(r'^xm|^羡慕|\?$|？$', self.msg):
            if (self.lastMsgInvl > Bot.SETTINGS['MIN_MSG_INVL']
                    and len(self.msg) <= Bot.SETTINGS['MAX_RND_XM_LEN']):
                myrand = random.random()
                if (myrand <= Bot.SETTINGS['RND_XM_PR']):
                    self.lastMsgInvl = 0
                    self.msg = re.sub(r'^我的|^我', '', self.msg)
                    self.res = '羡慕' + self.msg

    # avoid repaeting itself / another bot
    def checkWord(self):
        if self.res == self.msg and self.res in self.selfArr:
            self.res = ''
        else:
            for wordList in Bot.FIXED_REPLY_DICT.values():
                if self.msg in wordList:
                    self.res = ''
                    return
            self.selfArr[self.selfIndex] = self.res
            self.selfIndex = 0 if self.selfIndex == 9 else self.selfIndex + 1
            # TODO: rational delay time
            # sleepTimeRemain = (
            #     Bot.SETTINGS['SLEEP_TIME'] if Bot.SETTINGS['SLEEP_TIME'] != 0 else min(
            #         len(self.res) *
            #         0.25, 10)) + self.beginTimeStamp - time.time()
            # if (sleepTimeRemain > 0):
            #     time.sleep(sleepTimeRemain)

    def study(self):
        reg = re.search("问：(.+)\s+答：(.+)", self.msg)
        if reg and len(reg.groups()) == 2:
            ask = reg.groups()[0]
            ans = reg.groups()[1]
            if len(ask) <= 2:
                self.res = self.getReply("question_too_short")
                return
            if len(ans) >= 500:
                self.res = self.getReply("answer_too_long")
                return
            print(ask, ans)
            if Bot.STUDIED_REPLY.get(ask) is None:
                Bot.STUDIED_REPLY[ask] = {"answers": list(), "adders": list()}
            if ans not in Bot.STUDIED_REPLY[ask]["answers"]:
                Bot.STUDIED_REPLY[ask]["answers"].append(ans)
                Bot.STUDIED_REPLY[ask]["adders"].append(
                    self.context['user_id'])
                with open("study.json", 'w', encoding='UTF-8') as f:
                    json.dump(Bot.STUDIED_REPLY,
                              f,
                              ensure_ascii=False,
                              indent=4)
                self.res = self.getReply("study_successful")
            else:
                self.res = self.getReply("study_failed")

    def replyStudy(self):
        for key, value in Bot.STUDIED_REPLY.items():
            if key in self.msg:
                self.res = random.choice(value['answers'])
                return


if __name__ == "__main__":
    MyBot = Bot(123456)
