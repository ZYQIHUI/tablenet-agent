import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.core_agent import CoreAgent
from agents.tools.adapters.llm_body_client import LLMBodyClient
from agents.tools.adapters.llm_header_client import LLMHeaderClient
from agents.tools.adapters.llm_topic_client import LLMTopicClient
from agents.tools.rendering.renderer_tool import RendererTool
from agents.types import TableRequest


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num", type=int, default=1)
    parser.add_argument("--output", type=str, default="output/agent_table")
    parser.add_argument("--domain", type=str, default="telecommunications")
    parser.add_argument("--language", type=str, default="zh")
    parser.add_argument("--min_row", type=int, default=4)
    parser.add_argument("--max_row", type=int, default=12)
    parser.add_argument("--min_col", type=int, default=3)
    parser.add_argument("--max_col", type=int, default=8)
    parser.add_argument("--brower", type=str, default="chrome")
    parser.add_argument("--brower_width", type=int, default=1920)
    parser.add_argument("--brower_height", type=int, default=2440)
    parser.add_argument("--chrome_driver_path", type=str, default=None)
    parser.add_argument("--use_llm_topic", action="store_true")
    parser.add_argument("--llm_topic_api_key", type=str, default=None)
    parser.add_argument("--llm_topic_base_url", type=str, default=None)
    parser.add_argument("--llm_topic_model", type=str, default=None)
    parser.add_argument("--llm_topic_system_prompt", type=str, default=None)
    parser.add_argument("--use_llm_header", action="store_true")
    parser.add_argument("--llm_header_api_key", type=str, default=None)
    parser.add_argument("--llm_header_base_url", type=str, default=None)
    parser.add_argument("--llm_header_model", type=str, default=None)
    parser.add_argument("--llm_header_system_prompt", type=str, default=None)
    parser.add_argument("--use_llm_body", action="store_true")
    parser.add_argument("--llm_body_api_key", type=str, default=None)
    parser.add_argument("--llm_body_base_url", type=str, default=None)
    parser.add_argument("--llm_body_model", type=str, default=None)
    parser.add_argument("--llm_body_system_prompt", type=str, default=None)
    return parser.parse_args()


def find_default_chromedriver():
    for candidate in [
            Path("chromedriver-win64/chromedriver.exe"),
            Path("../chromedriver-win64/chromedriver.exe")]:
        if candidate.exists():
            return str(candidate)
    return None


def main():
    args = parse_args()
    if args.brower == "chrome" and args.chrome_driver_path is None:
        args.chrome_driver_path = find_default_chromedriver()
    request = TableRequest(
        domain=args.domain,
        language=args.language,
        min_rows=args.min_row,
        max_rows=args.max_row,
        min_cols=args.min_col,
        max_cols=args.max_col,
    )
    llm_topic_client = None
    if args.use_llm_topic:
        llm_topic_client = LLMTopicClient(
            api_key=args.llm_topic_api_key,
            base_url=args.llm_topic_base_url,
            model=args.llm_topic_model,
            system_prompt=args.llm_topic_system_prompt,
        )
    llm_header_client = None
    if args.use_llm_header:
        llm_header_client = LLMHeaderClient(
            api_key=args.llm_header_api_key,
            base_url=args.llm_header_base_url,
            model=args.llm_header_model,
            system_prompt=args.llm_header_system_prompt,
        )
    llm_body_client = None
    if args.use_llm_body:
        llm_body_client = LLMBodyClient(
            api_key=args.llm_body_api_key,
            base_url=args.llm_body_base_url,
            model=args.llm_body_model,
            system_prompt=args.llm_body_system_prompt,
        )
    core = CoreAgent(
        llm_topic_client=llm_topic_client,
        llm_header_client=llm_header_client,
        llm_body_client=llm_body_client,
        use_llm_topic=args.use_llm_topic,
        use_llm_header=args.use_llm_header,
        use_llm_body=args.use_llm_body,
    )
    tables = [core.generate(request) for _ in range(args.num)]
    renderer = RendererTool(
        output=args.output,
        brower=args.brower,
        brower_width=args.brower_width,
        brower_height=args.brower_height,
        chrome_driver_path=args.chrome_driver_path,
    )
    try:
        renderer.render_many(tables)
    finally:
        renderer.close()
    print(f"generated {args.num} agent tables into {args.output}")


if __name__ == "__main__":
    main()
