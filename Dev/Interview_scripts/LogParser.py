'''Given a list of log lines like:
"2024-03-01 09:31:05 ERROR FIX session dropped: EXCHANGE_A"
"2024-03-01 09:31:07 INFO Reconnecting to EXCHANGE_A"

Write a function that:
- Parses each line into (timestamp, level, message)
- Returns all ERROR lines within a given time window
- Counts errors per source (e.g. EXCHANGE_A, EXCHANGE_B)
'''
def parse_errors(logs, start_time=None, end_time=None):
    # logs: list of strings like "09:31:05 ERROR FIX_ENGINE Session dropped"
    # source: optional string to filter by
    results = []
    error_lines=[]

    error_count = {}

    for line in logs:
        print(line)
        date, timestamp, level, message = line.split(' ', 3)
        timestamp = date + " " + timestamp
        print(timestamp," ", level," ", message)
        results.append({"timestamp": timestamp, "level" : level, "message": message})

        if level == "ERROR":
            if start_time and timestamp < start_time:
                continue

            if end_time and timestamp > end_time:
                continue
                # Save matching error line
            error_lines.append((timestamp, level, message))

            if ":" in message:
                source = message.split(":")[-1].strip()
                print(source)
                if source not in error_count:
                    error_count[source] = 1
                else:
                    error_count[source] += 1

    return results,error_lines,error_count





logs = [
    "2024-03-01 09:31:05 ERROR FIX session dropped: EXCHANGE_A",
    "2024-03-01 09:31:07 INFO Reconnecting to EXCHANGE_A",
    "2024-03-01 09:31:10 ERROR Connection timeout: EXCHANGE_B",
    "2024-03-01 09:35:00 ERROR Feed disconnected: EXCHANGE_A"
]

output,error_lines,error_count = parse_errors(logs)
print("Lines are ",output)
print("Errors lines are :", error_lines)
print("Errors Count are :", error_count)

