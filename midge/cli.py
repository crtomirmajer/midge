import asyncio
import logging
from typing import Callable, Dict, List

import click

import midge
from midge import analysis, core, record
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
@click.argument('file_path', type=click.STRING)
@click.option('--analyze', '-a', type=bool, is_flag=True, help='Analyze LOGS after LOAD-TEST finishes')
def run(file_path: str, analyze: bool, ) -> None:
    swarms = import_midge_file(file_path)
    logs = _loop.run_until_complete(_run(swarms))
    logging.info(f'Logs are saved in {logs}')

    if analyze:
        for log in logs:
            reports = _analyze(log)
            logging.info(f'Report saved in {reports}')


@click.command(name='analyze', help='- Analyze LOG file and create a REPORT')
@click.argument('file_path', type=click.STRING)
def analyze(file_path: str) -> None:
    reports = _analyze(file_path)
    logging.info(f'Report saved in {reports}')


@click.command(name='compare', help='- Compare two REPORTS')
@click.argument('baseline', type=str, required=True)
@click.argument('report', type=str, required=True)
def compare(baseline: str, report: str) -> None:
    baseline_full = record.load(baseline, record.FullReport)
    report_full = record.load(report, record.FullReport)
    comparison = analysis.compare(baseline_full, report_full)

    print(record.dumps(comparison))


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

midgectl.add_command(run)
midgectl.add_command(analyze)
midgectl.add_command(compare)
