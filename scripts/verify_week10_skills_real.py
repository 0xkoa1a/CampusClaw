"""Capture actual guide/wrong-answer skill responses using synthetic questions."""
import argparse
import json
from pathlib import Path
import uuid

from scripts.verify_week06 import Api, TEACHER, STUDENT_A, STUDENT_B, login, create_conversation


def run(base_url):
    api=Api(base_url); tokens=[]; result={'mode':'CLab-real-gateway','cases':[]}
    try:
        teacher=login(api,*TEACHER); tokens.append(teacher)
        student=login(api,*STUDENT_A); tokens.append(student)
        foreign=login(api,*STUDENT_B); tokens.append(foreign)
        skills=api.json('GET','/api/skills',token=teacher)['skills']
        for name,trigger,question in (
            ('数学解题引导','方程,数学','方程2x+3=11，下一步该怎么检查？只给一个提示，不给最后的解。'),
            ('错题讲解','错题,检查','我把方程2x+3=11算成x=7，这道错题应先检查哪里？请指出错误原因，不给标准答案。'),
        ):
            skill=next((s for s in skills if s['name']==name and s['enabled']),None)
            if skill is None:
                source=f'名称：{name}\n适用条件：{trigger}\n工具：knowledge_search\n启用：是\n\n帮助学生发现下一步检查方法，不给最终答案或标准答案。'
                skill=api.json('POST','/api/skills',payload={'source':source},token=teacher,expected=201)['skill']
            agent=api.json('POST','/api/agents',payload={'name':'W10技能复核-'+uuid.uuid4().hex[:8],
                'role_prompt':'你是循序渐进的数学老师，给检查思路，不直接解出题目。',
                'enabled':True,'skill_ids':[skill['id']],'material_ids':[],'tool_names':[]},token=teacher,expected=201)['agent']
            cid=create_conversation(api,student,agent['id'])
            reply=api.stream(student,cid,question)
            assert reply.get('answer','').strip()
            result['cases'].append({'skill':name,'conversation_id':cid,'question':question,'actual_answer':reply['answer']})
        search=api.json('POST','/api/search',payload={'q':'SEC08_POISON','mode':'keyword'},token=foreign)
        assert search['hits']==[]
        result['cross_class_keyword_hits']=search['hits']
        result['transport_status']='passed'
        result['behavior_review']='inspect saved actual_answer; transport success alone is insufficient'
    finally:
        for token in tokens: api.json('POST','/api/logout',token=token)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-url',default='http://127.0.0.1:18100');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); result=run(a.base_url);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
