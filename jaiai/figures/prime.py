import random
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import plotly.express as px
import polars as pl
from wordcloud import WordCloud

from jaiai.figures.mask import IChart


class WordCloudFigure:

    @staticmethod
    def _tokenize(
        s: str, split_pat: re.Pattern, strip_chars: str
    ) -> list[tuple[str, str]]:
        """
        Возвращает список (orig, norm), где:
            - orig — токен после strip(strip_chars), для вывода;
            - norm — norm_orig.casefold(), для сравнения со стоп-словами.
        Пустые токены отбрасываются.
        """
        out: list[tuple[str, str]] = []
        for t in split_pat.split(s):
            if not t:
                continue
            orig = t.strip(strip_chars)
            if not orig:
                continue
            out.append((orig, orig.casefold()))
        return out

    @staticmethod
    def color_func(*_args, **_kwargs):

        return f"hsl({random.randint(0, 360)}, 70%, 40%)"

    def _count_freqs_by_tokens(
        self,
        tokens: list[tuple[str, str]],
        stopwords: set[str],
        split_pat: re.Pattern,
        strip_chars: str = ".,:;!?()[]{}\"'«»`~…/\\|*#@%^&+=\t\r",
    ) -> dict[str, int]:

        n = len(tokens)

        norms = [t[1] for t in tokens]

        # --- подготавливаем словарь фраз-стоп-слов: длина -> set(tuple(norm_tokens))

        phrase_by_len: dict[int, set] = {}
        max_len = 1
        for sw in stopwords:
            phrase_tokens = self._tokenize(sw, split_pat, strip_chars)
            if not phrase_tokens:
                continue
            key = tuple(tok_norm for _, tok_norm in phrase_tokens)
            L = len(key)
            max_len = max(max_len, L)
            phrase_by_len.setdefault(L, set()).add(key)

        # Если нет стоп-слов — ничего не делаем

        if not phrase_by_len:
            return dict(Counter(norms))
            # cleaned_tokens = [orig for orig, _ in tokens]
            # return cleaned_tokens, " ".join(cleaned_tokens)

        # --- сканирование «длиннейшим первым»

        drop = [False] * n
        i = 0
        while i < n:
            matched = False
            if not drop[i]:
                # пробуем от max_len к 1
                for L in range(min(max_len, n - i), 0, -1):
                    if any(drop[i : i + L]):
                        continue
                    window = tuple(norms[i : i + L])
                    if window in phrase_by_len.get(L, ()):
                        for j in range(i, i + L):
                            drop[j] = True
                        i += L
                        matched = True
                        break
            if not matched:
                i += 1

        # --- собираем результат
        cleaned_tokens = [orig for (k, (orig, _)) in enumerate(tokens) if not drop[k]]
        return dict(Counter(cleaned_tokens))

    def render(
        self,
        text: str,
        width: int = 800,
        height: int = 400,
        stopwords: list[str] | None = None,
        syms_to_split: Iterable[str] = (" ", "\n", "-"),
        strip_chars: str = ".,:;!?()[]{}\"'«»`~…/\\|*#@%^&+=\t\r",
        only_json: bool = False,
    ):

        split_pat = re.compile("|".join(re.escape(s) for s in syms_to_split))

        tokens = self._tokenize(text, split_pat, strip_chars)  # [(orig, norm), ...]
        js_freqs = self._count_freqs_by_tokens(
            tokens,
            stopwords=set(stopwords or []),
            split_pat=split_pat,
            strip_chars=strip_chars,
        )

        wc = WordCloud(
            width=width,
            height=height,
            background_color=None,  # прозрачный фон
            mode="RGBA",
            font_path=None,
            prefer_horizontal=0.9,
            collocations=False,
            color_func=self.color_func,
        ).generate_from_frequencies(js_freqs)

        words = []

        for (word, freq), font_size, position, orientation, color in wc.layout_:

            x, y = position

            # В wordcloud ориентация хранится как константы PIL (или None)

            rotate = 90 if orientation == 1 else 0

            words.append(
                {
                    "text": word,
                    "freq": float(freq),
                    "fontSize": int(font_size),
                    "x": int(x),
                    "y": int(y),
                    "rotate": int(rotate),
                    "color": color,  # уже готовый цвет
                    # по желанию можно добавить: "fontFamily": "sans-serif"
                }
            )

        return words, wc


class PlotlyScatterChart(IChart):
    def view(
        self,
        data: pl.DataFrame,
        label_to_view: str = "title",
        max_label_length: int = 22,
        logo_path: str | None = None,
        **props,
    ) -> Any:
        pl_data = data.rename({"label": label_to_view})
        pl_data = pl_data.with_columns(
            pl.col(label_to_view).apply(
                lambda x: (
                    (x[:max_label_length] + "...") if len(x) > max_label_length else x
                )
            )
        )
        pd_data = pl_data.to_pandas()
        fig = px.scatter(
            pd_data,
            x="x",
            y="y",
            color=label_to_view,
            hover_data={label_to_view: True, "text": False},
        )
        fig.update_layout(
            plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white")
        )

        if logo_path is not None:
            fig.add_layout_image(
                dict(
                    source=str(
                        Path(__file__).parent.parent / "builtins" / "Logo.jpg"
                    ),  # Path to your logo file  # noqa: F821
                    xref="paper",
                    yref="paper",
                    x=1,
                    y=1,
                    sizex=0.1,
                    sizey=0.1,
                    xanchor="right",
                    yanchor="bottom",
                )
            )

        # # Add a "Powered by" text next to the logo
        # fig.add_annotation(
        # dict(
        #     x=0.98,
        #     y=1.1,
        #     xref='paper',
        #     yref='paper',
        #     text="Powered by",
        #     showarrow=False,
        #     font=dict(
        #         family="Arial",
        #         size=12,
        #         color="Cyan"
        #     ),
        #     align="right"
        # )
        # )

        return fig

    def save(self, filename, **kwargs):
        self.chart.write_image(filename, **kwargs)
