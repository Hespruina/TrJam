import math
import asyncio
import json
import os
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder, CommandResponse
from utils.api_utils import call_onebot_api
from utils.task_utils import create_monitored_task

logger = get_logger("MBTILoveCommand")

# 存储用户答题状态
user_status = {}
# 存储待撤回的问题消息ID
pending_question_messages = {}

# 构建概率表（用于智能推断）
prob_table = None

# 问题列表
questions = [
    {
        "title": "问题1. 去游乐园玩的话，下面哪个项目你最喜欢?",
        "options": {
            "A": "和玩偶们互动",
            "B": "比较刺激的过山车之类",
            "C": "比较悠闲的旋转木马之类",
            "D": "不爱去游乐园"
        }
    },
    {
        "title": "问题2. 去超市买新鲜的水果or菜时，你更喜欢挑选:",
        "options": {
            "A": "被工作人员包好贴好价签的",
            "B": "散放着可以自己挑选称重的"
        }
    },
    {
        "title": "问题3. 下面几种尺寸的毛绒玩偶，你最喜欢?",
        "options": {
            "A": "小小的，可以挂在包上的",
            "B": "中等的，可以塞在包里的",
            "C": "比较大的，可以抱在怀里",
            "D": "超级大的，可以整个抱住的",
            "E": "都可以，全都喜欢"
        }
    },
    {
        "title": "问题4. 看电影电视剧的时候，你很容易代入到某个角色中吗?",
        "options": {
            "A": "是的，总是不由自主的代入",
            "B": "不，更喜欢上帝视角看整个剧情"
        }
    },
    {
        "title": "问题5. 你的梦一般是有逻辑的还是混乱的?",
        "options": {
            "A": "有逻辑的，清晰的",
            "B": "混乱的，无序的",
            "C": "逻辑与混乱并存"
        }
    },
    {
        "title": "问题6. 衣柜里的一些不常穿的旧衣服，你会清理掉吗?",
        "options": {
            "A": "会，放着太占地方了",
            "B": "不会，都承载了一些记忆"
        }
    },
    {
        "title": "问题7. 你发现自己失眠时一般会:",
        "options": {
            "A": "听听催眠的音乐或者吃点药，想办法睡着",
            "B": "顺其自然，玩一会别的困了再睡",
            "C": "想东想西，有点焦虑",
            "D": "其他"
        }
    },
    {
        "title": "问题8. 在亲近的人面前你并不介意表现出自己的缺点?",
        "options": {
            "A": "不怎么介意，在亲近的人面前无法避免",
            "B": "介意，因为亲近才想变得更好"
        }
    }
]

# 答案集合（心理学完善版）
answer_sets = {
    "纵欲型": set([
        # 核心特征：高冲动性、低回避、高焦虑依恋、享乐主义
        # 典型组合：问题1选B(刺激), 问题2选B(自由), 问题3选D/E(强烈需求), 问题5选B(混乱), 问题7选B(顺其自然)
        "bbdbaaba", "bbdeaaba", "bbdbabaa", "bbdeabaa", "bbdbaabb",  # 典型组合
        "bbdbcaaa", "bbdecaaa", "bbdbdaaa", "bbdedaaa", "bbdebaaa",  # 边缘组合
        "abdbaaba", "abdeaaba", "cbdbaaba", "cbdeaaba", "dbdbaaba",  # 问题1变体
        "bbdbaaca", "bbdeaaca", "bbdbabca", "bbdeabca", "bbdbaacc",  # 问题8变体
        "bbdbcaab", "bbdecaab", "bbdbdaab", "bbdedaab", "bbdebaab",  # 问题6变体
        "bbdbcbab", "bbdecbab", "bbdbdbab", "bbdedbab", "bbdebbab",  # 问题4变体
        "bbdbccba", "bbdeccba", "bbdbdcba", "bbdedcba", "bbdebcba",  # 问题5变体
        "bbdbcaaa", "bbdecaaa", "bbdbdaaa", "bbdedaaa", "bbdebaaa",  # 问题7变体
        "aabaaaaa", "aabbaaaa", "aaaabaaa", "aababaaa", "bababaaa",  # 原有有效组合
        "cababaaa", "dababaaa", "abbabaaa", "aacabaaa", "abcabaaa", 
        "aadabaaa", "abdabaaa", "aaeabaaa", "aaabbaaa", "aabbbaaa", 
        "cabbbaaa", "aadbbaaa", "aaaacaaa", "caaacaaa", "daaacaaa", 
        "abaacaaa", "aabacaaa", "babacaaa", "cabacaaa", "dabacaaa", 
        "abbacaaa", "bbbacaaa", "cbbacaaa", "aacacaaa", "cacacaaa", 
        "dacacaaa", "abcacaaa", "aadacaaa", "cadacaaa", "dadacaaa"
    ]),
    "痴迷型": set([
        # 核心特征：高焦虑依恋、高回避、强烈占有欲、浪漫主义
        # 典型组合：问题1选C(安全), 问题2选A(规则), 问题3选D(强烈需求), 问题4选A(代入), 问题7选C(焦虑)
        "cadabbcb", "cadacbcb", "badabbcb", "badacbcb", "caeabbcb",  # 典型组合
        "cadabcbb", "cadacbbb", "badabcbb", "badacbbb", "caeadbbb",  # 边缘组合
        "cababbcb", "cacabbcb", "cbdaabcb", "cbdaacbb", "cbdaabbb",  # 问题1变体
        "caeaabcb", "caeaacbb", "caeaabbb", "caeaacbc", "caeaabbc",  # 问题3变体
        "cadabbcc", "cadacbcc", "badabbcc", "badacbcc", "caeabccc",  # 问题8变体
        "cadabbca", "cadacbca", "badabbca", "badacbca", "caeabcba",  # 问题6变体
        "baaaaaaa", "bbdabaaa", "bbaacaaa", "bbcacaaa", "baeacaaa",  # 原有有效组合
        "badbcaaa", "babaabaa", "bbcaabaa", "dadaabaa", "bbdaabaa", 
        "baababaa", "babbabaa", "cadbabaa", "bababbaa", "dacabbaa", 
        "aadabbaa", "dadabbaa", "baeabbaa", "baaacbaa", "abdacbaa", 
        "baeacbaa", "daeacbaa", "bbeacbaa", "baabcbaa", "bbabcbaa", 
        "bbbbcbaa", "bacbcbaa", "cacbcbaa", "badbcbaa", "cadbcbaaa",
        "bbdbcbaa", "baebcbaa", "badaaaba", "badacaba", "baaaabba",
        "bbaaabba", "babaabba", "bbbaabba", "bacaabba", "bbcaabba", 
        "badaabba", "dadaabba", "bbdaabba", "cadbabba"
    ]),
    "救赎型": set([
        # 核心特征：高尽责性、高宜人性、工具性依恋、利他主义
        # 典型组合：问题1选C(安全), 问题2选A(规则), 问题3选D(需求), 问题4选A(代入), 问题7选A(解决问题)
        "cadaabaa", "cadacbaa", "badaabaa", "badacbaa", "caeaabaa",  # 典型组合
        "cadaabab", "cadacbab", "badaabab", "badacbab", "caeaabab",  # 边缘组合
        "cabaaaba", "cacaaaba", "cbdaaaba", "cbdaaabb", "cbdaaabc",  # 问题1变体
        "caeaacaa", "caeaacab", "caeaacac", "caeaacad", "caeaacae",  # 问题6变体
        "cadaabca", "cadacbca", "badaabca", "badacbca", "caeaabca",  # 问题7变体
        "cadaabcb", "cadacbcb", "badaabcb", "badacbcb", "caeaabcb",  # 问题8变体
        "caaaaaaa", "cbaaaaaa", "caaabaaa", "abaabaaa", "bbaabaaa",  # 原有有效组合
        "cbaabaaa", "cbbabaaa", "cacabaaa", "cbcabaaa", "cadabaaa", 
        "cbdabaaa", "caeabaaa", "cbeabaaa", "caabbaaa", "cbabbaaa", 
        "cbaacaaa", "cbcacaaa", "cbdacaaa", "caaaabaa", "bbaaabaa", 
        "cbaaabaa", "cabaabaa", "cbbaabaa", "cacaabaa", "cbcaabaa", 
        "cbdaabaa", "caeaabaa", "cbeaabaa", "caababaa", "cbababaa", 
        "aaaabbaa", "caaabbaa", "daaabbaa", "abaabbaa", "bbaabbaa", 
        "cbaabbaa", "dbaabbaa", "cababbaa", "abbabbaa", "bbbabbaa", 
        "cbbabbaa", "dbbabbaa", "cacabbaa", "abcabbaa"
    ]),
    "现实型": set([
        # 核心特征：高尽责性、低神经质、工具性依恋、实用主义
        # 典型组合：问题1选D(回避), 问题2选A(规则), 问题3选A/B(实用), 问题4选B(客观), 问题5选A(逻辑)
        "daabaaab", "dabbaaab", "caabaaab", "cabbaaab", "baabaaab",  # 典型组合
        "daababab", "dabbabab", "caababab", "cabbabab", "baababab",  # 边缘组合
        "dbaaabaa", "dbbaabaa", "dcababaa", "ddababaa", "deababaa",  # 问题1变体
        "daabacaa", "dabbacaa", "caabacaa", "cabbacaa", "baabacaa",  # 问题3变体
        "daabadaa", "dabbadaa", "caabadaa", "cabbadaa", "baabadaa",  # 问题4变体
        "daabaead", "dabbaead", "caabaead", "cabbaeaa", "baabaead",  # 问题5变体
        "daaaaaaa", "abaaaaaa", "bbaaaaaa", "dbaaaaaa", "dabaaaaa",  # 原有有效组合
        "bbbaaaaa", "cbbaaaaa", "dbbaaaaa", "dacaaaaa", "abcaaaaa", 
        "bbcaaaaa", "cbcaaaaa", "dbcaaaaa", "dadaaaaa", "abdaaaaa", 
        "bbdaaaaa", "cbdaaaaa", "dbdaaaaa", "baeaaaaa", "caeaaaaa", 
        "daeaaaaa", "abeaaaaa", "bbeaaaaa", "cbeaaaaa", "dbeaaaaa", 
        "aaabaaaa", "baabaaaa", "caabaaaa", "daabaaaa", "ababaaaa", 
        "bbabaaaa", "cbabaaaa", "dbabaaaa", "babbaaaa", "cabbaaaa", 
        "dabbaaaa", "abbbaaaa", "bbbbaaaa", "cbbbaaaa", "dbbbaaaa", 
        "aacbaaaa", "cacbaaaa", "dacbaaaa", "abcbaaaa"
    ]),
    "游戏型": set([
        # 核心特征：低回避、低焦虑、享乐主义、关系流动性
        # 典型组合：问题1选B(刺激), 问题2选B(自由), 问题3选E(开放), 问题4选B(客观), 问题7选B(随性)
        "bbebbaba", "bbebcaba", "bbcbabaa", "bbcbcbaa", "bbecbaba",  # 典型组合
        "bbebbabb", "bbebcabb", "bbcbabab", "bbcbcbaa", "bbecbabb",  # 边缘组合
        "abeababa", "aceababa", "bceababa", "cdeababa", "deeababa",  # 问题1变体
        "bbeababa", "bbeacaba", "bbcababa", "bbcacaba", "bbecacaa",  # 问题3变体
        "bbeababb", "bbeacabb", "bbcababb", "bbcacabb", "bbecacab",  # 问题4变体
        "bbeababc", "bbeacabc", "bbcababc", "bbcacabc", "bbecacac",  # 问题5变体
        "bacaaaaa", "bacbaaaa", "baaabaaa", "bacabaaa", "bbcabaaa",  # 原有有效组合
        "baeabaaa", "baabbaaa", "babbbaaa", "aacbbaaa", "bacbbaaa", 
        "cacbbaaa", "bbcbbaaa", "badbbaaa", "cadbbaaa", "baebbaaa", 
        "baabcaaa", "bacbcaaa", "bacbabaa", "baabbbaa", "babbbbaa", 
        "aacbbbaa", "bacbbbaa", "bbcbbbaa", "baebbbaa", "bacaaaba", 
        "bbcaaaba", "baabaaba", "babbaaba", "bacbaaba", "cacbaaba", 
        "bbcbaaba", "badbaaba", "baebaaba", "baaababa", "bbaababa", 
        "bacababa", "bbcababa", "badababa", "bbdababa", "baeababa", 
        "bbeababa", "baabbaba", "caabbaba", "bbabbaba"
    ]),
    "友伴型": set([
        # 核心特征：安全型依恋、高宜人性、低神经质、渐进式亲密
        # 典型组合：问题1选C(安全), 问题2选B(自由), 问题3选C(适度), 问题4选A(代入), 问题5选C(混合)
        "cbcacbba", "cbcaccba", "abcacbba", "abcaccba", "cbbacbba",  # 典型组合
        "cbcacbbb", "cbcacccc", "abcacbbb", "abcacccc", "cbbacccc",  # 边缘组合
        "abaaabaa", "abcaabaa", "abdaabaa", "aaababaa", "abababaa",  # 原有有效组合
        "bbababaa", "abbbabaa", "aacbabaa", "abcbabaa", "aadbabaa", 
        "abdbabaa", "aaabbbaa", "ababbbaa", "abbbbbaa", "abcbbbaa", 
        "abdbbbaa", "ababcbaa", "abcbcbaa", "abdbcbaa", "ababaaba", 
        "abaaabba", "aaababba", "caababba", "abababba", "bbababba", 
        "cbababba", "abbbabba", "bbbbabba", "cbbbabba", "abcbabba", 
        "cbcbabba", "abdbabba", "cbdbabba", "abebabba", "ababbbba", 
        "abcbbbba", "abdbbbba", "abebbbba", "ababcbba", "ababaaca", 
        "ababbaca", "abaaabca", "abcaabca", "aaababca",
        # 新增：安全型依恋核心组合
        "cbcacbba", "cbcaccba", "abcacbba", "abcaccba", "cbbacbba", 
        "cbcacbca", "cbcaccca", "abcacbca", "abcaccca", "cbbacbca", 
        "cbcacbab", "cbcacccb", "abcacbab", "abcacccb", "cbbacbab", 
        "cbcacbac", "cbcacccc", "abcacbac", "abcacccc", "cbbacbac", 
        # 新增：渐进式亲密特征组合
        "cbcacbaa", "cbcaccaa", "abcacbaa", "abcaccaa", "cbbacbaa", 
        "cbcacbaa", "cbcaccaa", "abcacbaa", "abcaccaa", "cbbacbaa", 
        "cbcacbaa", "cbcaccaa", "abcacbaa", "abcaccaa", "cbbacbaa"
    ])
}

# 构建类型-选项分布概率表
def build_probability_table():
    # 初始化计数器: {type: {question_index: {option: count}}}
    counts = {ptype: [{} for _ in range(8)] for ptype in answer_sets}
    
    # 统计每个类型中各题目的选项分布
    for ptype, patterns in answer_sets.items():
        for ans_str in patterns:
            # 只处理前8个字符（因为只有8个问题）
            for i, char in enumerate(ans_str[:8]):
                opt = char.upper()
                counts[ptype][i][opt] = counts[ptype][i].get(opt, 0) + 1
    
    # 计算概率分布: P(option|type, question)
    prob_table = {}
    for ptype in counts:
        prob_table[ptype] = []
        total_patterns = len(answer_sets[ptype])
        
        for i in range(8):
            # 获取当前题目的选项总数（用于平滑）
            num_options = len(questions[i]["options"])
            question_probs = {}
            
            # 计算每个选项的概率（使用拉普拉斯平滑）
            for opt in ['A', 'B', 'C', 'D', 'E']:
                count = counts[ptype][i].get(opt, 0)
                # 平滑处理：避免零概率
                prob = (count + 1) / (total_patterns + num_options)
                question_probs[opt] = prob
            
            prob_table[ptype].append(question_probs)
    
    return prob_table

# 解析文本
interpretations = {
    "纵欲型": """1.纵欲型
>爱恋人格:直球吸引·热烈【纵欲型】
>爱欲倾向:
>重情 21%  重欲 79%
>激情 68%  理智 32%
>守护 33%  依恋 67%
---
【纵欲型】是：  
会在情感上相当直接地表达自己的需求,不想压抑自身欲望也不违背内心意愿,更不想以后后悔看中情感的纯粹性,如果吸引力无法维系情感就直接了当地放弃。
你渴望：  
忠于内心,正视欲望,不被外物所牵绊的热烈之爱。相爱不用想太多,享受情浓之时的甜蜜,也要接受散场之后的落寞。享受体验而非追逐结果，感受愉悦而非承担责任。
你排斥：  
来自情感与道德的绑架,赌上一生重量的压迫不谈情深先谈将来,过于现实而忽视感情的本质对已失去的仍挽回,藕断丝连纠缠不清。
---
😊可以贴贴:直球吸引的热烈【纵欲型】
😫禁止接触:清醒务实的守护【现实型】""",
    "痴迷型": """2.痴迷型
>爱恋人格:偏执占有·纯情【痴迷型】
>爱欲倾向:
>重情 75%  重欲 25%
>激情 83%  理智 17%
>守护 26%  依恋 74%
---
【痴迷型】是：  
对爱人有强烈的占有欲,不容任何人染指。不喜欢在爱里投注过多理性,喜欢浪漫温柔的美好特质。喜欢一个人就会给与所有自己能给的,义无反顾且热烈。
你渴望：  
绝对的偏爱,目光绝不投之于他人身上的 1v1 关系。事事有回应,件件有结果,发自内心的在意。双向的爱与奔赴,付出被看见被回应
你排斥：  
玩弄感情,满口谎言,以虚伪换取真心  
说了喜欢却半途而废,在爱里退缩的胆小鬼  
权衡得失,把别人的爱放在天平上称量而后决定取舍
---
😊可以贴贴:易感共情的真诚【救赎型】
😫禁止接触:清醒务实的守护【现实型】""",
    "救赎型": """3.救赎型
>爱恋人格:易感共情·真诚【救赎型】
>爱欲倾向:
>重情 96%  重欲 4%
>激情 84%  理智 16%
>守护 78%  依恋 22%
---
【救赎型】是：  
习惯占据主动位置,喜欢被依赖被深爱的感觉 不怕在感情里付出,想用自己的力量改变 be 美学的结局有种敢逆命而行的执着,爱上了就会死磕到底。
你渴望：  
爱意栖息在值得的人身上 ,双向救赎。成为某个人的港湾,爱是软肋但也能成为铠甲。找到与自己严丝合缝的那块拼图,补足不完美的自己。
你排斥：  
不谈付出只顾索取,功利性地想从爱中得到什么。多疑多思,真心总被试探质疑。以情绪为由行伤害之实,将缺点无限放大后不断指责
---
😊可以贴贴:偏执占有的纯情【痴迷型】
😫禁止接触:清醒务实的守护【现实型】""",
    "现实型": """4.现实型
>爱恋人格:清醒务实·守护【现实型】
>爱欲倾向:
>重情 87%  重欲 13%
>激情 9%  理智 91%
>守护 95%  依恋 5%
---
【现实型】是：  
兼顾爱与责任,不擅长制造浪漫但会从细枝末节践行爱意。注重实际,并不耽于虚空的浪漫舍弃实用的面包 。说到做到,把约定放在心上,并不爱空口许诺。
你渴望：  
真心换真心的交往,共担风雨长相厮守 。发自内心的爱意,基于理性思考后建立的羁绊。彼此尊重彼此理解,可以吵架但不可以互相伤害。
你排斥：  
把感情当乐子,只是玩玩而已的浪子。三分钟热度,上头时爱生爱死下头时有始无终。嘴上说着爱,心里却只当成一门生意。
---
😊可以贴贴:慢热渐进的长情【友伴型】
😫禁止接触:拥抱此刻的享乐【游戏型】""",
    "游戏型": """5.游戏型
>爱恋人格:拥抱此刻·享乐【游戏型】
>爱欲倾向:
>重情 58%  重欲 42%
>激情 72%  理智 28%
>守护 12%  依恋 88%
---
【游戏型】是：  
有着开放且自洽的恋爱观,并不被传统的价值观限制。视恋爱为游戏,认为"快乐"就是爱情的唯一责任。喜欢就会认真对待,不爱了也能坦荡分开。
你渴望：  
纯粹而坦诚的感情,情感与欲望都有栖息之处 。彼此相伴着走过一段路,共同拥有一段美好的时光。可以有争吵,可以有结束,但不要一丁点的虚伪和敷衍。
你排斥：  
一味用花里胡哨的套路雕饰爱意,标榜真诚却不见实意。感情已经散了却还*死缠烂打*,试图用时间和过去来绑架。满口天长地久海誓山盟,自以为爱比金坚。
---
😊可以贴贴:直球吸引的热烈【纵欲型】
😫禁止接触:偏执占有的纯情【痴迷型】""",
    "友伴型": """6.友伴型
>爱恋人格:慢热渐进.长情【友伴型】
>爱欲倾向:
>重情 91%  重欲 9%
>激情 33%  理智 67%
>守护 55%  依恋 45%
---
【友伴型】是:  
性格较为被动,更喜欢默默思考而非大声表达 。对外界有很好的共情力,对自己的情感却很后知后觉。对爱情没有轰轰烈烈的想象,只有细水长流的期盼。
你渴望：  
循序渐进慢慢培养的感情*,有基石的感情而非空中楼阁。足够的尊重足够的理解,同进退共前行。无言的付出被看见,无声的爱意被接收。
你排斥：  
未经允许就擅自靠近,没怎么相处就直接越界。快餐式的感情,尚未抵达内心深处却标榜深情。说的比唱的还好听,行动却完全跟不上。
---
😊可以贴贴:清醒务实的守护【现实型】
😫禁止接触:易感共情的真诚【救赎型】"""
}

# 异步消息撤回函数

# 发送合并转发消息函数
async def send_group_forward_message(context, group_id, messages):
    """发送群合并转发消息"""
    try:
        payload = {
            'group_id': group_id,
            'messages': messages
        }
        
        logger.info(f"执行合并转发消息API调用：send_group_forward_msg，群号：{group_id}")
        logger.debug(f"请求参数：{payload}")
        
        # 执行onebot API请求
        result = await call_onebot_api(
            context=context,
            action='send_group_forward_msg',
            params=payload
        )
        
        if result is None:
            return False, "API请求失败，未获取到响应"
        
        if result.get('success'):
            return True, "合并转发消息发送成功"
        else:
            error_msg = result.get('error', '未知错误')
            return False, f"API调用失败：{error_msg}"
    except Exception as e:
        logger.error(f"发送合并转发消息时发生异常: {e}")
        return False, f"发送消息时发生错误：{str(e)}"

# 发送下一个问题函数
async def send_next_question(context, user_id, group_id, current_index=0):
    """发送下一个问题"""
    cache_key = f"{group_id}_{user_id}"
    
    # 初始化或更新用户状态
    if cache_key not in user_status:
        user_status[cache_key] = {
            "answers": [],
            "current_index": 0
        }
    
    # 更新当前问题索引
    user_status[cache_key]["current_index"] = current_index
    
    # 检查是否所有问题都已回答完
    if current_index >= len(questions):
        # 所有问题都已回答完，计算结果
        return await calculate_result(context, user_id, group_id)
    
    # 获取当前问题
    question = questions[current_index]
    
    # 构建问题消息
    builder = MessageBuilder(context)
    builder.set_group_id(group_id)
    builder.set_user_id(user_id)
    builder.add_at()
    builder.add_text(f"\n{question['title']}\n")
    
    for key, desc in question["options"].items():
        builder.add_text(f"{key}. {desc}\n")
    
    builder.add_text(f"\n请使用指令回复选项字母（如：/mbti-love A）")
    builder.add_text(f"\n这是第 {current_index + 1}/{len(questions)} 题")
    
    # 发送问题并保存消息ID用于后续撤回
    async def callback(message_id):
        if message_id:
            pending_question_messages[cache_key] = message_id
    
    builder.set_callback(callback)
    await builder.send()
    
    return CommandResponse.none()

# 计算测试结果函数
async def calculate_result(context, user_id, group_id):
    """计算测试结果并发送"""
    cache_key = f"{group_id}_{user_id}"
    
    # 获取用户答案
    if cache_key not in user_status:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("\n❌ 未找到您的答题记录，请重新开始测试")
        await builder.send()
        return CommandResponse.none()
    
    answers = user_status[cache_key]["answers"]
    
    # 确保有8个答案
    if len(answers) != len(questions):
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("\n❌ 答题记录不完整，请重新开始测试")
        await builder.send()
        return CommandResponse.none()
    
    # 构建答案字符串
    answer_str = ''.join(answers)
    
    # 精确匹配
    matched_type = None
    for personality, patterns in answer_sets.items():
        if answer_str in patterns:
            matched_type = personality
            break
    
    # 智能推断（贝叶斯概率模型）
    if matched_type is None:
        # 懒加载：确保prob_table已初始化
        global prob_table
        if prob_table is None:
            prob_table = build_probability_table()
        # 计算每个类型的可能性 P(type|answers) ∝ P(answers|type) * P(type)
        # 假设先验概率P(type)相等，只需计算似然 P(answers|type) = ∏ P(option_i|type, question_i)
        scores = {}
        for ptype in prob_table:
            log_prob = 0.0  # 使用对数避免下溢
            for i, char in enumerate(answer_str.upper()):
                # 获取该选项在当前类型中的条件概率
                prob = prob_table[ptype][i].get(char, 1e-10)  # 防御性处理
                log_prob += math.log(prob)
            scores[ptype] = log_prob
        
        # 选择概率最高的类型
        matched_type = max(scores, key=scores.get)
    
    # 保存用户测试结果
    await save_user_result(user_id, matched_type, answer_str)
    
    # 构建合并转发消息
    forward_messages = []
    
    # 获取机器人自身信息作为发送者
    bot_user_id = context.get_config_value("bot_qq", "bot")  # 使用机器人QQ号或默认值
    bot_nickname = context.get_config_value("bot_name", "ZHRrobot")  # 使用机器人名称或默认值
    
    # 添加测试回顾消息
    review_content = f"🧡 爱恋人格测试回顾 🧡\n\n"  
    review_content += f"您的答题结果: {answer_str}\n\n"
    
    for i, (question, answer) in enumerate(zip(questions, answers)):
        review_content += f"问题{i+1}: {question['title']}\n"
        review_content += f"您的选择: {answer.upper()}. {question['options'][answer.upper()]}\n\n"
    
    review_message_node = {
        'type': 'node',
        'data': {
            'user_id': bot_user_id,
            'nickname': f"{bot_nickname}-爱情版MBTI",
            'content': [{"type": "text", "data": {"text": review_content}}]
        }
    }
    forward_messages.append(review_message_node)
    
    # 添加最终结果消息
    result_message_node = {
        'type': 'node',
        'data': {
            'user_id': bot_user_id,
            'nickname': f"{bot_nickname}-爱情版MBTI",
            'content': [{"type": "text", "data": {"text": interpretations[matched_type]}}]
        }
    }
    forward_messages.append(result_message_node)
    
    # 发送合并转发消息
    success, message = await send_group_forward_message(context, group_id, forward_messages)
    
    # 清理用户状态
    if cache_key in user_status:
        del user_status[cache_key]
    if cache_key in pending_question_messages:
        del pending_question_messages[cache_key]
    
    if success:
        # 发送完成提示
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("\n✅ 测试完成！您的爱恋人格分析已生成")
        await builder.send()
    else:
        # 发送失败提示
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f"\n❌ 生成结果失败: {message}")
        await builder.send()
    
    return CommandResponse.none()

# 保存用户测试结果
async def save_user_result(user_id, personality_type, answer_str):
    """保存用户测试结果到文件"""
    pass

# 查找匹配的群友
async def find_matching_users(context, group_id, current_user_id, current_user_type):
    """查找群内匹配的用户"""
    # 完全移除群成员匹配功能
    return None

# 命令处理器
async def handle_mbti_love_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> CommandResponse:
    """
    处理 /mbti-love 命令，用于进行爱恋人格测试
    """
    # 创建后台任务处理耗时的测试操作
    create_monitored_task(
        process_mbti_love_test(context, args, user_id, group_id),
        name=f"MBTILoveCommand_process_{user_id}_{group_id}"
    )
    
    # 返回none表示已经通过builder发送了消息
    return CommandResponse.none()

async def process_mbti_love_test(context: BotContext, args: list, user_id: str, group_id: str):
    """在后台处理MBTI爱情测试的耗时操作"""
    try:
        cache_key = f"{group_id}_{user_id}"
        
        # 检查是否有参数（可能是用户回答）
        if args:
            # 检查用户是否正在测试中
            if cache_key not in user_status:
                # 用户不在测试中，开始新的测试
                return await send_next_question(context, user_id, group_id)
            
            # 获取用户的回答
            answer = args[0].strip().upper()
            current_index = user_status[cache_key]["current_index"]
            
            # 验证回答是否有效
            current_question = questions[current_index]
            if answer not in current_question["options"]:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text(f"\n❌ 无效的选项，请重新输入")
                await builder.send()
                return CommandResponse.none()
            
            # 保存回答
            user_status[cache_key]["answers"].append(answer.lower())
            
            # 撤回问题消息
            if cache_key in pending_question_messages:
                await safe_recall_message(context, pending_question_messages[cache_key])
                del pending_question_messages[cache_key]
            
            # 发送下一个问题或计算结果
            return await send_next_question(context, user_id, group_id, current_index + 1)
        else:
            # 没有参数，开始新的测试
            # 如果用户已经在测试中，重置状态
            if cache_key in user_status:
                del user_status[cache_key]
            if cache_key in pending_question_messages:
                del pending_question_messages[cache_key]
            
            # 发送开始测试的提示
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text("\n💕 欢迎参加爱恋人格测试！\n")
            builder.add_text("本次测试共有8个问题，请根据你的直觉选择最符合的选项。\n")
            builder.add_text("让我们开始吧！")
            await builder.send()
            
            # 延迟发送第一个问题
            await asyncio.sleep(1)
            return await send_next_question(context, user_id, group_id)
    
    except Exception as e:
        logger.error(f"处理mbti-love命令异常: {e}")
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f"\n❌ 处理命令时发生错误: {str(e)}")
        await builder.send()
        return CommandResponse.none()

# 命令帮助信息
def get_command_help():
    return {
        "mbti-love": "进行爱恋人格测试，了解你的恋爱性格"  
    }

def main():
    # 使用全局定义的变量
    global prob_table
    
    print("欢迎参加爱恋人格测试！请根据你的直觉选择最符合的选项。\n")

    # 构建概率表（用于智能推断）
    prob_table = build_probability_table()

    answers = []
    for i, q in enumerate(questions, 1):
        print(f"问题{i}. {q['title']}")
        for key, desc in q["options"].items():
            print(f"{key}. {desc}")
        while True:
            choice = input("请选择（输入字母）: ").strip().upper()
            if choice in q["options"]:
                answers.append(choice.lower())
                break
            else:
                print("无效选项，请重新输入。")
        print()  # 空行分隔

    answer_str = ''.join(answers)
    print(f"你的答题结果: {answer_str}")

    # 精确匹配
    matched_type = None
    for personality, patterns in answer_sets.items():
        if answer_str in patterns:
            matched_type = personality
            break

    # 智能推断（贝叶斯概率模型）
    if matched_type is None:
        # 计算每个类型的可能性 P(type|answers) ∝ P(answers|type) * P(type)
        # 假设先验概率P(type)相等，只需计算似然 P(answers|type) = ∏ P(option_i|type, question_i)
        scores = {}
        for ptype in prob_table:
            log_prob = 0.0  # 使用对数避免下溢
            for i, char in enumerate(answer_str.upper()):
                # 获取该选项在当前类型中的条件概率
                prob = prob_table[ptype][i].get(char, 1e-10)  # 防御性处理
                log_prob += math.log(prob)
            scores[ptype] = log_prob
        
        # 选择概率最高的类型
        matched_type = max(scores, key=scores.get)
        
        # 调试信息（可选）
        print("\n智能推断分析:")
        print(f"根据你的答题模式，系统计算出以下概率分布:")
        for ptype, score in scores.items():
            # 转换为相对概率（归一化）
            relative_prob = math.exp(score - max(scores.values())) * 100
            print(f"- {ptype}: {relative_prob:.1f}%")
        print(f"\n最终推断结果: 【{matched_type}】")

    # 输出解析
    print("\n" + "="*50)
    print("你的爱恋人格测试结果如下：")
    print("="*50)
    print(interpretations[matched_type])

if __name__ == "__main__":
    # 确保概率表初始化
    if prob_table is None:
        prob_table = build_probability_table()
    main()

# 全局变量初始化将在使用时进行懒加载