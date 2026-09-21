select
    hour_number,
    printf('%02d:00', hour_number) as hour_label,
    case when hour_number between 6 and 9 then 'Morning peak'
         when hour_number between 16 and 19 then 'Evening peak'
         when hour_number < 6 then 'Overnight'
         else 'Off peak' end as time_band
from range(24) t(hour_number)
union all
select -1, 'Unknown', 'Unknown'
