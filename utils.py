import io
import json
import logging
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

logger = logging.getLogger(__name__)

def generate_chart_from_json(chart_json_str: str) -> io.BytesIO | None:
    """Generates a chart image from a JSON string using Matplotlib.

    Args:
        chart_json_str: A JSON string containing chart data (expected format
                          similar to Chart.js or Plotly basic structures).

    Returns:
        An io.BytesIO buffer containing the PNG image data, or None if generation fails.
    """
    try:
        chart_data = json.loads(chart_json_str)
        logger.debug(f"Successfully parsed chart JSON: {chart_data}")

        chart_type = chart_data.get('type', 'bar').lower() # Default to bar chart
        data = chart_data.get('data')
        options = chart_data.get('options', {})

        if not data or 'labels' not in data or 'datasets' not in data or not data['datasets']:
            logger.error("Invalid or incomplete chart data structure in JSON.")
            return None

        labels = data['labels']
        datasets = data['datasets']

        plt.style.use('seaborn-v0_8-darkgrid') # Use a nice style
        fig, ax = plt.subplots(figsize=(10, 6)) # Adjust figure size as needed

        # --- Plotting Logic based on chart_type ---
        if chart_type == 'bar':
            num_datasets = len(datasets)
            bar_width = 0.8 / num_datasets # Adjust width based on number of datasets
            x = range(len(labels))

            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                # Ensure data length matches labels length
                if len(dataset_data) != len(labels):
                    logger.warning(f"Dataset {i} data length mismatch. Padding or truncating.")
                    # Simple padding/truncating - adjust as needed
                    dataset_data = (dataset_data + [0] * len(labels))[:len(labels)]

                # Calculate position for each bar group
                bar_positions = [pos + i * bar_width - (bar_width * (num_datasets -1) / 2) for pos in x]
                ax.bar(bar_positions, dataset_data, bar_width, label=dataset.get('label', f'Dataset {i+1}'))

            ax.set_xticks([pos + bar_width * (num_datasets -1) / 2 - (bar_width * (num_datasets -1) / 2) for pos in x]) # Center ticks
            ax.set_xticklabels(labels, rotation=45, ha="right")

        elif chart_type == 'line':
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                # Ensure data length matches labels length
                if len(dataset_data) != len(labels):
                    logger.warning(f"Dataset {i} data length mismatch. Padding or truncating.")
                    dataset_data = (dataset_data + [0] * len(labels))[:len(labels)]
                ax.plot(labels, dataset_data, marker='o', linestyle='-', label=dataset.get('label', f'Dataset {i+1}'))
            plt.xticks(rotation=45, ha="right")

        elif chart_type == 'pie':
            # Pie charts typically use only the first dataset
            if datasets:
                dataset = datasets[0]
                dataset_data = dataset.get('data', [])
                # Ensure data length matches labels length
                if len(dataset_data) != len(labels):
                    logger.warning(f"Pie chart data length mismatch. Padding or truncating.")
                    dataset_data = (dataset_data + [0] * len(labels))[:len(labels)]

                # Filter out zero values to avoid clutter/errors
                non_zero_data = [d for d in dataset_data if d > 0]
                non_zero_labels = [labels[i] for i, d in enumerate(dataset_data) if d > 0]

                if non_zero_data:
                    ax.pie(non_zero_data, labels=non_zero_labels, autopct='%1.1f%%', startangle=90)
                    ax.axis('equal') # Equal aspect ratio ensures a circular pie chart
                else:
                    logger.warning("No non-zero data available for pie chart.")
                    ax.text(0.5, 0.5, 'No data to display', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)
            else:
                 logger.warning("No datasets found for pie chart.")
                 ax.text(0.5, 0.5, 'No data to display', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)

        else:
            logger.warning(f"Unsupported chart type: '{chart_type}'. Defaulting to bar chart visualization if possible.")
            # Fallback or error - could try to render as bar chart anyway
            # For simplicity, we'll just return None here if type is unknown
            plt.close(fig)
            return None

        # --- Common Chart Customizations ---
        ax.set_title(options.get('title', 'Biểu đồ phân tích')) # Get title from options or default
        ax.set_xlabel(options.get('xAxisLabel', ''))
        ax.set_ylabel(options.get('yAxisLabel', 'Giá trị'))

        # Format Y-axis to be more readable (e.g., using commas for thousands)
        formatter = mticker.FuncFormatter(lambda x, p: format(int(x), ','))
        ax.yaxis.set_major_formatter(formatter)

        if datasets and len(datasets) > 1:
            ax.legend()

        plt.tight_layout() # Adjust layout to prevent labels overlapping

        # Save chart to a BytesIO buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig) # Close the plot to free memory
        logger.info(f"Successfully generated {chart_type} chart image.")
        return buf

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode chart JSON string: {e}")
        logger.debug(f"Problematic JSON string: {chart_json_str}")
        return None
    except Exception as e:
        logger.error(f"Failed to generate chart: {e}", exc_info=True)
        if 'fig' in locals() and plt.fignum_exists(fig.number):
             plt.close(fig) # Ensure figure is closed on error
        return None
