"""rerun_demo_loop workflow — validation-driven rerun end-to-end (BL-062).

mock backend（--mock bash）：agent prompt 作为 shell 命令执行。

阶段 make 运行 rerun_probe.sh——首次（fail-flag 存在）exit 1 并消费 flag，
回退重跑时 flag 已不存在 → exit 0。命令用 `code=$?; ...; exit $code` 让
**agent 事件流的退出码反映 probe 真实结果**（P0-1 修复：此前 `echo $?` 后
未 exit，事件 exit_code 恒 0/127，语义倒置）。
feedback（路由决策 message）以 shell 注释 `# [路由反馈] ...` 追加——
shell 注释天然免疫中文/引号/换行，不会作为命令执行（P0-1 修复）。
validate() 读 make_exit.txt：非 0 → RouteDecision("make", message)；0 → None。
"""

from pathlib import Path

_LOOP_DIR = Path(__file__).resolve().parent


def run(agent, state, **kwargs):
    from loopflow.domain.rerun_loop import Stage, run_rerun_loop

    make_cmd = (
        f"bash {_LOOP_DIR / 'rerun_probe.sh'} fail-flag.txt; "
        f"code=$?; echo $code > make_exit.txt; exit $code"
    )
    stages = [
        Stage(name="make", prompt=make_cmd, label="make"),
        Stage(name="check", prompt="echo check-done", label="check"),
    ]

    # 失败标记在阶段外创建一次：make 第 1 次失败并消费 flag，回退重跑时
    # flag 已不存在 → 第 2 次成功（这正是要演示的 validation-driven rerun）。
    Path("fail-flag.txt").write_text("1")

    def validate():
        from loopflow.domain.rerun_loop import RouteDecision

        exit_file = Path("make_exit.txt")
        if exit_file.is_file():
            code = exit_file.read_text().strip()
            if code == "0":
                return None
            return RouteDecision("make",
                                 message=f"make 阶段退出码 {code}（期望 0）：产物未就绪，需重跑")
        return RouteDecision("make", message="make 阶段无退出码文件：视为失败，需重跑")

    def stage_fn(stage, context):
        from loopflow.domain.rerun_loop import RerunOutcome

        # 信息传递通道：重跑阶段把 feedback（路由决策 message）以 shell 注释
        # 形式追加——P0-1 修复：裸追加会被 mock bash 当作命令执行（exit 127）
        feedback = context.get("feedback")
        prompt = stage.prompt
        if feedback:
            prompt = f"{prompt}\n# [路由反馈] {feedback}"
        # session 恢复通道：回退重跑时携带该阶段上次调用的 session id
        resume = context.get("resume_session_id")
        if resume:
            prompt = f"{prompt}\n# [session 恢复] 继续上次会话 {resume}"
        result = agent(prompt, label=stage.label,
                       resume_session_id=resume if resume else None)
        # 返回 RerunOutcome：sid 从 AgentResult.session_id 取（mock 下为 None）
        sid = getattr(result, "session_id", None)
        return RerunOutcome(value=result, session_id=sid)

    result = run_rerun_loop(
        stages,
        validate=validate,
        route_map={"make": "make"},
        budget=2,
        stage_fn=stage_fn,
        emit_log=lambda m: print(m, flush=True),
    )

    # 把回退轨迹写入 state（框架 State 持久化演示）
    state.rerun_result = {
        "status": result.status,
        "reruns": result.reruns,
        "stages_run": result.stages_run,
    }
    return {"status": result.status, "reruns": result.reruns,
            "stages_run": result.stages_run}
