dayfactor = eval(input('enter improvement rate: '))
def improve(df):
    dayup = 1
    for i in range(365):
        if i % 7 in [6, 0]:
            dayup = dayup * (1 - 0.01)
        else:
            dayup =dayup *  (1+ df)
    return dayup
while improve(dayfactor) < 37.78:
    dayfactor += 0.001
print('result:{:.3f}'.format(dayfactor))