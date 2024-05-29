import asyncio

from metagpt.environment import Environment
from metagpt.roles import Role
from metagpt.actions import Action, UserRequirement
from metagpt.logs import logger
from metagpt.schema import Message
from metagpt.team import Team
from metagpt.utils.common import OutputParser



class WriteInstruction(Action):

    name: str = "WriteInstruction"

    PROMPT_TEMPLATE: str = """
        您现在是短篇小说领域经验丰富的小说作家内容规划师, 我们需要您根据给定的{msg}要求，来完成小说题材生成故事的基本结构。
        按照以下内容输出符合给定题材的小说基本结构：
        标题:"小说的标题"
        设置:"小说的情景设置细节，包括时间段、地点和所有相关背景信息"
        主角:"小说主角的名字、年龄、职业，以及他们的性格和动机、简要的描述"
        反派角色:"小说反派角色的名字、年龄、职业，以及他们的性格和动机、简要的描述"
        冲突:"小说故事的主要冲突，包括主角面临的问题和涉及的利害关系"
        对话:"以对话的形式描述情节，揭示人物，以此提供一些提示给读者"
        主题:"小说中心主题，并说明如何在整个情节、角色和背景中展开"
        基调:"整体故事的基调，以及保持背景和人物的一致性和适当性的说明"
        节奏:"调节故事节奏以建立和释放紧张气氛，推进情节，创造戏剧效果的说明"
        其它:"任何额外的细节或对故事的要求，如特定的字数或题材限制"
        """
    async def run(self, msg: str):
        prompt = self.PROMPT_TEMPLATE.format(msg = msg)
        rsp = await self._aask(prompt)
        return rsp


class ChapterGenerate(Action):

    name: str = "ChapterGenerate"

    PROMPT_TEMPLATE: str = """
        您现在是短篇小说领域经验丰富的小说作家章节规划师, 我们需要您根据给定的{content}小说基本结构，创作出小说的目录和章节内容概况。
        总共创作出十章的目录和章节内容概况，请按照以下要求提供该小说的具体目录和目录中的故事概况：
        1. 输出必须严格符合指定语言。
        2. 回答如下: "第一章：章节标题": "故事概况", "第二章：章节标题": "故事概况" 等。
        3. 目录应尽可能引人注目和充分，包括一级目录和本章故事概况。
        4. 不要有额外的空格或换行符。
        5. 不需要重复写出目录
        """
    async def run(self, content: str):
        prompt = self.PROMPT_TEMPLATE.format(content = content)
        rsp = await self._aask(prompt)
        return rsp


class ContentGenerate(Action):

    name: str = "ContentGenerate"

    PROMPT_TEMPLATE: str = """
        您现在是短篇小说领域经验丰富的小说作家。请以引人入胜的风格，深入细致地按照故事概况"{content}"写出故事内容，可以从环境描述，人物对话，人物心理以及动作细节上多描述一点，尽量写1000字左右。
        注意与上一章故事内容的衔接，上一章故事内容为{topic}。 
        """
    async def run(self, content: str, topic: str):
        prompt = self.PROMPT_TEMPLATE.format(content = content, topic=topic)
        rsp = await self._aask(prompt)
        return rsp


class Instructor(Role):

    name: str = "hk"
    profile: str = "Instructor"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([WriteInstruction])
        self._watch([UserRequirement])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: ready to {self.rc.todo}")
        todo = self.rc.todo

        msg = self.get_memories()

        instruct_text = await WriteInstruction().run(msg)
        logger.info(f"Instructor: {instruct_text}")
        msg = Message(content=instruct_text, role=self.profile, cause_by=type(todo))

        return msg


class ChapterGenerator(Role):

    name: str = "cg"
    profile: str = "ChapterGenerator"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([ChapterGenerate])
        self._watch([WriteInstruction])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: ready to {self.rc.todo}")
        todo = self.rc.todo

        msg = self.get_memories()
        chapter_text = await ChapterGenerate().run(msg)
        logger.info(f"ChapterGenerator: {chapter_text}")
        msg = Message(content=chapter_text, role=self.profile, cause_by=type(todo))

        return msg


class ContentGenerator(Role):

    name: str = "cong"
    profile: str = "ContentGenerator"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([ContentGenerate])
        self._watch([ChapterGenerate])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: ready to {self.rc.todo}")
        todo = self.rc.todo
        chapters_directory = str(self.get_memories(k=1)[-1].content).split("\n\n")
        story = []
        main_topic = str(self.get_memories()[0].content)
        title = str(self.get_memories()[1].content).split("\n")[0]
        story.append(title)
        content = None
        for i, chapter_dir in enumerate(chapters_directory):
            if i == 0:
                topic = main_topic
                content = chapter_dir
            else:
                topic = content
                content = chapter_dir
            content_text = await ContentGenerate().run(content=content, topic=topic)
            story.append(content_text)
        all_story = "\n".join(story)
        with open("story.txt", 'w') as f:
            f.write(all_story)
        msg = Message(content=all_story, role=self.profile, cause_by=type(todo))
        return msg
        # for i in range(1, 11):
        #     # if i == 1:
        #     #     msg = Message(k=i, content=self.get_memories(k=1)[0].content)
        #     # else:
        #     msg = self.get_memories()
        #     content_text = await ContentGenerate().run(msg)
        #     logger.info(f"ChapterGenerator: {content_text}")
        #     msg = Message(content=content_text, role=self.profile, cause_by=type(todo))

        # return msg


env = Environment()

async def main(topic: str, n_round=13):
    env.add_roles([Instructor(), ChapterGenerator(), ContentGenerator()])
    env.publish_message(
        Message(role="Human", content=topic, cause_by=UserRequirement)
    )
    while n_round > 0:
        n_round -= 1
        await env.run()

    return env.history

asyncio.run(main(topic="写一篇和游戏主题相关的小说，一万字左右。情节如下：勇士的爱人被怪物抓走了，勇士背上武器就去救爱人，旅途中在小怪物手中救了很多伙伴，这些伙伴陪伴勇士一起去打败最后的怪物，救出了公主！"))


