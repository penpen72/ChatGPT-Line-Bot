# import opencc

# s2t_converter = opencc.OpenCC('s2t')
# t2s_converter = opencc.OpenCC('t2s')


def get_role_and_content(response: str):
    role = response['choices'][0]['message']['role']
    content = response['choices'][0]['message']['content'].strip()
    # content = s2t_converter.convert(content)
    return role, content

def get_tool_calls(response: str):
    tool_calls = response['choices'][0]['message'].get('tool_calls')
    # function_name = [tool_call['function']['name'] for tool_call in tool_calls ]
    return tool_calls