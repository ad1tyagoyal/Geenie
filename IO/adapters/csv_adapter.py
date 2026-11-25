from pathlib import Path
from typing import Any

import polars as pl


class CSVAdapter:
    """Adapter for reading and writing Polars DataFrames to CSV files."""

    def read(self, path: str | Path, **kwargs: Any) -> pl.DataFrame:
        """Read a CSV file into a Polars DataFrame.

        Args:
            path: Path to the input CSV file.
            **kwargs: Additional keyword arguments forwarded to `polars.read_csv`.

        Returns:
            A Polars DataFrame containing the CSV data.
        """
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(f"CSV file not found: {source}")
        return pl.read_csv(source, **kwargs)

    def write(
        self,
        df: pl.DataFrame,
        path: str | Path,
        *,
        create_dirs: bool = True,
        **kwargs: Any,
    ) -> Path:
        """Write a Polars DataFrame to a CSV file.

        Args:
            df: The Polars DataFrame to write.
            path: Destination CSV file path.
            create_dirs: Whether to create missing parent directories.
            **kwargs: Additional keyword arguments forwarded to `DataFrame.write_csv`.

        Returns:
            The resolved destination `Path` that was written.
        """
        if not isinstance(df, pl.DataFrame):
            raise TypeError(f"Expected a polars.DataFrame, got {type(df).__name__}")

        target = Path(path)
        if create_dirs:
            target.parent.mkdir(parents=True, exist_ok=True)

        df.write_csv(target, **kwargs)
        return target
