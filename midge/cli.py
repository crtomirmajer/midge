import asyncio
import logging
from typing import Callable, Dict, List

import click

import midge
from midge import analysis, core, record, visualize
from midge.utils import import_midge_file

print(f""" 
                     ,-.
         `._        /  |        
            `--._  ,   '    _,-'     888b     d888 8888888 8888888b.   .d8888b.  8888888888
     _       __  `.|  / ,--'         8888b   d8888   888   888   Y88b d88P  Y88b 888       
      `-._,-'  `-. \ : /             88888b.d88888   888   888    888 888    888 888       
     ,--.-.-.-.-.-`'.'.-.,-          888Y88888P888   888   888    888 888        8888888   
     '--'-'-'-'-'-;.'.'-'`-          888 Y888P 888   888   888    888 888  88888 888       
     _,-' `-.__,-' / : \\             888  Y8P  888   888   888    888 888    888 888      
                _,'|  \ `--._        888   "   888   888   888  .d88P Y88b  d88P 888       
           _,--'   '   .     `-.     888       888 8888888 8888888P"   "Y8888P88 8888888888
         ,'         \  |       
                      -’             v{midge.__version__}          
    """)

_loop = asyncio.get_event_loop()
logging.basicConfig(format='level=%(levelname)s time="%(asctime)s" message="%(message)s"', level=logging.INFO)


@click.group()
def midgectl() -> None:
    pass


@click.command(name='run', help='- Run a LOAD-TEST and output a LOG file')
@click.argument('task_path', type=click.STRING)
@click.option('--analyze', '-a', type=bool, is_flag=True, help='Analyze LOGS after LOAD-TEST finishes')
def run_command(task_path: str, analyze: bool, ) -> None:
    swarms = import_midge_file(task_path)
    logs = _loop.run_until_complete(_run(swarms))
    logging.info(f'Logs are saved in {logs}')

    if analyze:
        for log in logs:
            reports = _analyze(log)
            logging.info(f'Report saved in {reports}')


@click.command(name='analyze', help='- Analyze LOG file and create a REPORT')
@click.argument('log_path', type=click.STRING)
def analyze_command(log_path: str) -> None:
    reports = _analyze(log_path)
    logging.info(f'Report saved in {reports}')


@click.command(name='compare', help='- Compare two REPORTS')
@click.argument('baseline_path', type=str, required=True)
@click.argument('report_path', type=str, required=True)
def compare_command(baseline_path: str, report_path: str) -> None:
    baseline_full = record.load(baseline_path, record.FullReport)
    report_full = record.load(report_path, record.FullReport)
    comparison = analysis.compare(baseline_full, report_full)

    print(record.dumps(comparison))


@click.command(name='visualize', help='- Visualize LOG file')
@click.argument('file_path', type=str, required=True)
def visualize_command(file_path: str) -> None:
    if file_path.endswith('.log'):
        visualize.log(file_path)
    elif file_path.endswith('.report'):
        visualize.report(file_path)


async def _run(swarms: Dict[str, Callable[[], core.Swarm]]) -> List[str]:
    files = []
    for name, init_swarm in swarms.items():
        swarm = init_swarm()

        await swarm.setup()
        logs = await swarm.run()
        await swarm.teardown()

        log_file = f'{name.lower()}.log'
        record.dump(logs, log_file)
        files.append(log_file)

    return files


def _analyze(log_file: str) -> str:
    logs = record.load(log_file, List[record.ActionLog])
    name = log_file.split('.')[0]
    report = analysis.analyze(logs)
    report_file = f'{name}.report'
    record.dump(report, report_file)
    return report_file


midgectl.add_command(run_command)
midgectl.add_command(analyze_command)
midgectl.add_command(compare_command)
midgectl.add_command(visualize_command)
