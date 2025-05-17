# Number of days per month. First value placeholder for indexing purposes
month_days = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def is_leap(year):
    """Return true for leap years, false for non leap years"""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def days_in_month(year, month):
    """Return number of days in that month in that year."""
    if not 1 <= month <= 12:
        return 'Invalid Month!'
    elif month == 2 and is_leap(year):
        return 29
    else:
        return month_days[month]
    
print('Number of days in Month {}, year {} is = {}'.format(2, 2024, days_in_month(2024, 2)))
print('Number of days in Month {}, year {} is = {}'.format(10, 2124, days_in_month(2124, 10)))
print('Number of days in Month {}, year {} is = {}'.format(2, 3040, days_in_month(3040, 2)))

     