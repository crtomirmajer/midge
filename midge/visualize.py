from typing import List

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from midge.record import ActionLog
import midge.record as record

BINS = 50


def log(file_name: str):
    logs = record.load(file_name, List[ActionLog])
    time_series = to_time_series(logs, BINS)
    df = pd.DataFrame([record.dumpd(x) for x in time_series])

    ax1 = plt.subplot2grid((9, 1), (0, 0), rowspan=7)
    ax2 = plt.subplot2grid((9, 1), (7, 0))
    ax3 = plt.subplot2grid((9, 1), (8, 0))

    _plot_response_times(ax1, df)
    _plot_requests(ax2, df)
    _plot_success(ax3, df)

    plt.subplots_adjust()
    plt.savefig(f'{file_name}.svg', format='svg')
    plt.show()


def to_time_series(logs: List[ActionLog], bins: int):
    logs = sorted(logs, key=lambda o: o.start)

    # get time boundary
    start_time = logs[0].start
    end_time = logs[-1].start

    # get intervals
    min_bin = start_time
    diff_time = end_time - start_time
    bin_duration = (diff_time / bins)

    time_series = []
    timepoint = 0

    # build time-series aggregated on N time-points
    for log in logs:
        if log.start >= (min_bin + bin_duration):
            timepoint += 1
            min_bin += bin_duration
            if timepoint > bins - 1:
                break
        datapoint = record.DataPoint(log.action, timepoint, (log.end - log.start), int(log.success))
        time_series.append(datapoint)
    return time_series


def _plot_response_times(ax, df):
    ax.grid(which='major', axis='y', linestyle=':')
    sns.lineplot(x='timepoint', y='response_time', hue='action', data=df,
                 markers=True,
                 style='action',
                 ci=95,
                 ax=ax)
    ax.set_ylim(bottom=0)
    ax.set_xlim(0, BINS - 1)
    ax.set_xlabel('')
    ax.set_xticks([])
    ax.get_yaxis().set_label_coords(-0.04, 0.5)


def _plot_requests(ax, df):
    sns.countplot(x='timepoint', hue='action', data=df, ax=ax)
    ax.set_xlabel('')
    ax.set_ylabel('action')
    ax.set_xticks([])
    ax.legend().set_visible(False)
    ax.get_yaxis().set_label_coords(-0.04, 0.5)


def _plot_success(ax, df):
    sns.barplot(x='timepoint', y='success', color='green', data=df, ax=ax, alpha=0.6)
    ax.legend().set_visible(False)
    ax.get_yaxis().set_label_coords(-0.04, 0.5)
