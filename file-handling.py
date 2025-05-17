import re

def read_file(file_path):
    """Read the content of a file and return it as a list of lines."""
    with open(file_path, "r") as file:
        data = file.read()
    return data

def find_utc_date_strings(line):
    """Find all UTC date strings in a line."""
    date_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,9}Z'
    dates = re.findall(date_pattern, line)
    return dates

def format_text(lines):
    """Format each line by ensuring it begins with a UTC date string."""
    formatted_lines = []
    for line in lines:
        stripped_line = line.strip()
        dates = find_utc_date_strings(stripped_line)
        if dates:
            for index, date in enumerate(dates):
                # Find the log text that follows the UTC date string
                log_text = stripped_line.split(date, 1)[1].strip()

                if index + 1 < len(dates):
                    log_text = log_text.split(dates[index+1], 1)[0].strip()

                if len(log_text) > 0:
                    formatted_line = f"{date} {log_text}"
                    formatted_lines.append(formatted_line)
        else:
            # If no date is found, you might want to handle this case differently
            formatted_lines.append(stripped_line)
    return formatted_lines    

def write_file(file_path, lines):
    """Write the formatted lines to a new file"""
    with open(file_path, "w") as file:
        file.write('\n'.join(lines))

def main():
    input_file = "log-full.txt"
    output_file ="formatted-log-full.txt"

    lines = read_file(input_file)
    formatted_lines = format_text(lines)
    write_file(output_file, formatted_lines)
    print("Formatted log saved to {0}".format(output_file))


if __name__ == "__main__":
    main()