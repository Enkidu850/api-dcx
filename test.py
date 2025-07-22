import time
import sys

def progress_bar_decorator(func):
    def wrapper(*args, **kwargs):
        total = kwargs.get('total', 100)
        prefix = kwargs.get('prefix', '')
        suffix = kwargs.get('suffix', '')
        length = kwargs.get('length', 50)
        fill = kwargs.get('fill', '█')
        
        def print_progress_bar(iteration):
            percent = ("{0:.1f}").format(100 * (iteration / float(total)))
            filled_length = int(length * iteration // total)
            bar = fill * filled_length + '-' * (length - filled_length)
            sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
            sys.stdout.flush()
        
        for i in range(total):
            func(*args, **kwargs)
            print_progress_bar(i + 1)
            time.sleep(0.1)  # Simulate work being done
        
        print()  # Print New Line on Complete
    return wrapper

@progress_bar_decorator
def example_function(*args, **kwargs):
    # Simulate some work being done
    for i in range(1000000):
        pass

example_function(total=100, prefix='Progress', suffix='Complete', length=50, fill='+')