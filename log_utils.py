import io
import logging

import pandas as pd


def log_dataframe_info(df: pd.DataFrame) -> None:
    logging.info(dataframe_info_to_str(df))


def dataframe_info_to_str(df: pd.DataFrame) -> str:
    buffer = io.StringIO()
    df.info(buf=buffer)
    info_str = buffer.getvalue()
    return info_str


def column_names_and_types_to_str(df: pd.DataFrame) -> str:
    colum_names_and_types = [(col, df[col].dtype) for col in df.columns]
    return "\n".join([f"{col} {dtype}" for col, dtype in colum_names_and_types])
