from pprint import pprint
from typing import List

import click

import midge
from midge import core, record
from midge.core import ActionLog
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


@click.group()
def midgectl() -> None:
    pass


@click.command(name='run', help='- Run a LOAD-TEST and output a LOG file')
@click.option('--file-path', '-f', type=str, required=True, help='Midge LOAD-TEST definition file (.py)')
@click.option('--analyze', '-a', type=bool, is_flag=True, help='Analyze LOGS after LOAD-TEST is finished')
def run(file_path: str, analyze_logs: bool) -> None:
    swarm_constructors = import_midge_file(file_path)
    files = []

    for name, constructor in swarm_constructors.items():
        swarm = constructor()
        logs = swarm.run()

        log_file = f'{name}.log'
        record.dump(logs, name)

        files.append(log_file)

    if analyze_logs:
        analyze(files)


@click.command(name='analyze', help='- Analyze LOG file(s) and create a REPORT')
@click.option('--files', '-f', type=str, required=True, multiple=True, help='Load-Test LOG file(s)')
def analyze(files: List[str]) -> None:
    reports = {}
    for file_name in files:
        logs: List[ActionLog] = record.load(file_name, ActionLog)
        name = file_name.split('.')[0]
        report = core.analyze(logs)
        report[name] = report

    pprint(record.dumps(reports))


@click.command(name='compare', help='- Compare two REPORTS')
@click.option('--baseline', '-b', type=str, required=True, help='Baseline REPORT file')
@click.option('--report', '-r', type=str, required=True, help='New REPORT file')
def compare(baseline_file: str, report_file: str) -> None:
    baseline_full = record.load(baseline_file)
    report_full = record.load(report_file)
    comparison = core.compare(baseline_full, report_full)

    pprint(record.dumps(comparison))


midgectl.add_command(run)
midgectl.add_command(analyze)
midgectl.add_command(compare)
