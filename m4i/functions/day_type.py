from datetime import datetime

def day_type_week(dt: datetime) -> str:
        wd = dt.isoweekday() % 7

        if wd == 0:
            return "sunday"
        elif wd == 1:
            return "monday"
        elif wd == 5:
            return "friday"
        elif wd == 6:
            return "saturday"
        else:
            return "weekday"
        
def day_type_workday(dt: datetime) -> str:
        wd = dt.isoweekday() % 7

        if wd in (0,6):
            return "weekend"
        else:
            return "weekday"        

day_type = day_type_workday