from typing import Sequence

import numpy as np
from matplotlib import pyplot as plt

T_IMAGES = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]


def show_four_way(images: T_IMAGES, fig_title: str = None, fig_texts: Sequence[str] = None):
    titles = (
        "THRESHOLD MASK",
        "DILATED THRESHOLD MASK",
        "ORIGINAL",
        "PROCESSED",
    )
    fig, axes = plt.subplots(
        nrows=2,
        ncols=2,
        figsize=(10, 10),
        tight_layout=False,
    )
    axes = axes.flatten()
    for ax, image, title in zip(axes, images, titles):
        ax.imshow(image)
        ax.set(title=title)
        ax.axis("off")

    if fig_title:
        plt.suptitle(
            fig_title,
            fontsize=10,
        )

    if fig_texts:
        distance = 1.0 / (len(fig_texts) + 1)
        x = 1.0 / (len(fig_texts) + 3)
        for fig_text in fig_texts:
            plt.figtext(
                x, 0.12,
                fig_text,
                verticalalignment="top",
                horizontalalignment="left",
                fontsize=10,
            )
            x += distance

    plt.show()


def save_four_way(fig_title: str, filename: str, images: T_IMAGES):
    print(f"{fig_title=}, {filename=}")
    titles = (
        "dilated_cc_mask",
        "temp_dilated_cc_mask",
        "threshold_mask",
        "intersection",
    )
    fig, axes = plt.subplots(
        nrows=2,
        ncols=2,
        figsize=(10, 10),
        tight_layout=False,
    )
    axes = axes.flatten()
    for ax, image, title in zip(axes, images, titles):
        ax.imshow(image)
        ax.set(title=title)
        ax.axis("off")

    plt.suptitle(fig_title)
    plt.savefig(filename)
    plt.close()
