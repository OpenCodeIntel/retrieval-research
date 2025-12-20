"""
Test Suite for Click Code Search
=================================
50 queries for Click CLI framework (Python)

Categories:
1. Commands - Creating CLI commands
2. Options - Command line options
3. Arguments - Positional arguments
4. Output - Echo, style, colors
5. Input - Prompts, confirmation
6. Groups - Command groups
7. Types - Parameter types
8. Testing - CLI testing utilities
"""

CLICK_GROUND_TRUTH = [
    # ==========================================================================
    # 1. COMMANDS (10 queries)
    # ==========================================================================
    
    ("create cli command", ["command", "add_command", "Command"], "commands"),
    ("add command to group", ["add_command", "command"], "commands"),
    ("get command by name", ["get_command", "resolve_command"], "commands"),
    ("list all commands", ["list_commands", "format_commands"], "commands"),
    ("invoke command", ["invoke", "main", "__call__"], "commands"),
    ("get command path", ["command_path", "info_name"], "commands"),
    ("format command help", ["format_help", "format_commands", "get_help"], "commands"),
    ("resolve command name", ["resolve_command", "get_command"], "commands"),
    ("create command decorator", ["command", "decorators"], "commands"),
    ("pass context to command", ["pass_context", "make_pass_decorator"], "commands"),
    
    # ==========================================================================
    # 2. OPTIONS (8 queries)
    # ==========================================================================
    
    ("add option to command", ["add_option", "option"], "options"),
    ("create option decorator", ["option", "Option"], "options"),
    ("parse option value", ["_process_opts", "_match_long_opt"], "options"),
    ("handle boolean flag", ["flag_value", "is_flag"], "options"),
    ("set option default", ["default", "_format_default"], "options"),
    ("validate option", ["_process_opts", "type_cast_value"], "options"),
    ("get option from state", ["_get_value_from_state"], "options"),
    ("normalize option name", ["_normalize_opt", "_split_opt"], "options"),
    
    # ==========================================================================
    # 3. ARGUMENTS (6 queries)
    # ==========================================================================
    
    ("add argument to command", ["add_argument", "argument"], "arguments"),
    ("create argument decorator", ["argument", "Argument"], "arguments"),
    ("parse arguments", ["parse_args", "_process_args_for_args"], "arguments"),
    ("unpack argument values", ["_unpack_args", "_expand_args"], "arguments"),
    ("handle multiple arguments", ["nargs", "_process_args_for_args"], "arguments"),
    ("get argument encoding", ["_get_argv_encoding"], "arguments"),
    
    # ==========================================================================
    # 4. OUTPUT (8 queries)
    # ==========================================================================
    
    ("print to terminal", ["echo", "secho", "_echo"], "output"),
    ("print styled text", ["secho", "style", "echo"], "output"),
    ("apply text style", ["style", "_interpret_color"], "output"),
    ("remove text style", ["unstyle"], "output"),
    ("print via pager", ["echo_via_pager", "_echo"], "output"),
    ("clear terminal screen", ["clear"], "output"),
    ("format output", ["format_help", "format_usage"], "output"),
    ("wrap text output", ["wrap_text", "_flush_par"], "output"),
    
    # ==========================================================================
    # 5. INPUT (6 queries)
    # ==========================================================================
    
    ("prompt user for input", ["prompt", "prompt_func", "_build_prompt"], "input"),
    ("confirm user action", ["confirm"], "input"),
    ("hidden password input", ["hidden_prompt_func", "prompt"], "input"),
    ("get single character", ["_getchar", "getchar"], "input"),
    ("pause for user", ["pause", "_pause_echo"], "input"),
    ("edit in external editor", ["edit", "editor"], "input"),
    
    # ==========================================================================
    # 6. GROUPS (6 queries)
    # ==========================================================================
    
    ("create command group", ["group", "Group", "MultiCommand"], "groups"),
    ("invoke group command", ["invoke", "result_callback"], "groups"),
    ("chain commands together", ["_check_nested_chain", "chain"], "groups"),
    ("get group context", ["make_context", "Context"], "groups"),
    ("format group help", ["format_help", "format_commands"], "groups"),
    ("pass group obj", ["pass_obj", "make_pass_decorator"], "groups"),
    
    # ==========================================================================
    # 7. TYPES (6 queries)
    # ==========================================================================
    
    ("convert parameter type", ["convert", "type_cast_value"], "types"),
    ("create choice type", ["Choice", "convert"], "types"),
    ("create path type", ["Path", "resolve_path"], "types"),
    ("create file type", ["File", "_FileType"], "types"),
    ("validate range type", ["IntRange", "FloatRange", "_clamp"], "types"),
    ("create tuple type", ["Tuple", "convert"], "types"),
]

def get_test_queries():
    return [(q, exp) for q, exp, _ in CLICK_GROUND_TRUTH]

if __name__ == "__main__":
    print(f"Total queries: {len(CLICK_GROUND_TRUTH)}")
    categories = {}
    for _, _, cat in CLICK_GROUND_TRUTH:
        categories[cat] = categories.get(cat, 0) + 1
    print("\nQueries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    print("\n✅ Test suite ready for Click (Python CLI)")
