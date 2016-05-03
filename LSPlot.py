import os
import sys
import math
from collections import namedtuple

import pyodbc
import click
import matplotlib.pyplot as plt

import utils

GULLY = None
LANDSLIDE = None
HIGH_ESI = 25
MEDIUM_ESI = 8
LOW_ESI = 1.25
ALPHA = 2
DrainType = namedtuple('DrainType', 'GULLY LANDSLIDE ELSEWHERE')
DRAIN_TYPE = DrainType('gully', 'landslide', 'elsewhere')
conn = None


@click.command()
### Use the followings for debugging within PyCharm
#@click.option('--mdb', default=r"D:\Graip\GRAIPPythonTools\demo\demo_MWP\test.mdb", type=click.Path(exists=True))

# use the following for production
@click.option('--mdb', default="test.mdb", type=click.Path(exists=True))
@click.option('--high-esi', default=25.0, type=click.FLOAT)
@click.option('--medium-esi', default=8.0, type=click.FLOAT)
@click.option('--low-esi', default=1.25, type=click.FLOAT)
@click.option('--alpha', default=2.0, type=click.FLOAT)
def main(mdb, high_esi, medium_esi, low_esi, alpha):
    global HIGH_ESI, MEDIUM_ESI, LOW_ESI, ALPHA
    _validate_args(mdb, high_esi, medium_esi, low_esi, alpha)
    HIGH_ESI = high_esi
    MEDIUM_ESI = medium_esi
    LOW_ESI = low_esi
    ALPHA = alpha
    create_ls_plot(mdb)


def _validate_args(mdb, high_esi, medium_esi, low_esi, alpha):
    try:
        if not os.path.dirname(mdb):
            mdb = os.path.join(os.getcwd(), mdb)

        conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % mdb)
        conn.close()
    except pyodbc.Error as ex:
        raise utils.ValidationException(ex.message)

    err_msg = "Invalid value found for the parameter '{}'. Value must be greater than zero"
    if high_esi <= 0:
        raise utils.ValidationException(err_msg.format('--high-esi'))
    if medium_esi <= 0:
        raise utils.ValidationException(err_msg.format('--medium-esi'))
    if low_esi <= 0:
        raise utils.ValidationException(err_msg.format('--low-esi'))

    err_msg = "Invalid value found for the parameter '{}'."
    if high_esi != max(high_esi, medium_esi, low_esi):
        raise utils.ValidationException(err_msg.format('--high-esi') + " The specified value is not the highest value.")

    if low_esi != min(high_esi, medium_esi, low_esi):
        raise utils.ValidationException(err_msg.format('--low-esi') + " The specified value is not the lowest value.")

    if alpha <= 0:
        raise utils.ValidationException("Invalid value found for parameter '--alpha.'. Value must be more than zero.")


def create_ls_plot(graip_db):
    global GULLY
    global LANDSLIDE
    global ALPHA
    global conn
    conn = pyodbc.connect(utils.MS_ACCESS_CONNECTION % graip_db)
    cursor = conn.cursor()

    # get the IDs for Gully and Landslide from the DischargeToDefinitions table
    row = cursor.execute("SELECT DischargeToID FROM DischargeToDefinitions WHERE DischargeTo=?",
                         'Gully').fetchone()
    GULLY = row.DischargeToID

    row = cursor.execute("SELECT DischargeToID FROM DischargeToDefinitions WHERE DischargeTo=?",
                         'Landslide').fetchone()
    LANDSLIDE = row.DischargeToID

    dp_rows = cursor.execute("SELECT Slope, ELength, ESI, DischargeToID FROM DrainPoints ORDER BY Slope").fetchall()

    # variable of type list to store data points for points plot
    dp_slope_values_gully = []
    dp_elength_values_gully = []
    dp_slope_values_landslide = []
    dp_elength_values_landslide = []
    dp_slope_values_others = []
    dp_elength_values_others = []

    # variable of type list to store data points for line plots
    HIGH_ESI_elength_values = []
    MEDIUM_ESI_elength_values = []
    LOW_ESI_elength_values = []
    ESI_slope_values = []

    # variable of type dict to store statistics data
    count_ESI_ge_HIGH_ESI = {DRAIN_TYPE.GULLY: 0, DRAIN_TYPE.LANDSLIDE: 0, DRAIN_TYPE.ELSEWHERE: 0}
    count_ESI_lt_HIGH_ESI_ge_MEDIUM_ESI = {DRAIN_TYPE.GULLY: 0, DRAIN_TYPE.LANDSLIDE: 0, DRAIN_TYPE.ELSEWHERE: 0}
    count_ESI_lt_MEDIUM_ESI_ge_LOW_ESI = {DRAIN_TYPE.GULLY: 0, DRAIN_TYPE.LANDSLIDE: 0, DRAIN_TYPE.ELSEWHERE: 0}
    count_ESI_lt_LOW_ESI = {DRAIN_TYPE.GULLY: 0, DRAIN_TYPE.LANDSLIDE: 0, DRAIN_TYPE.ELSEWHERE: 0}

    for dp_row in dp_rows:
        slope_in_deg = math.atan(dp_row.Slope) * 180/math.pi
        if dp_row.DischargeToID == GULLY:
            dp_slope_values_gully.append(slope_in_deg)
            dp_elength_values_gully.append(dp_row.ELength)
            _compute_statistics(dp_row.ELength, dp_row.Slope, GULLY, count_ESI_ge_HIGH_ESI,
                                count_ESI_lt_HIGH_ESI_ge_MEDIUM_ESI,
                                count_ESI_lt_MEDIUM_ESI_ge_LOW_ESI, count_ESI_lt_LOW_ESI)
        elif dp_row.DischargeToID == LANDSLIDE:
            dp_slope_values_landslide.append(slope_in_deg)
            dp_elength_values_landslide.append(dp_row.ELength)
            _compute_statistics(dp_row.ELength, dp_row.Slope, LANDSLIDE, count_ESI_ge_HIGH_ESI,
                                count_ESI_lt_HIGH_ESI_ge_MEDIUM_ESI,
                                count_ESI_lt_MEDIUM_ESI_ge_LOW_ESI, count_ESI_lt_LOW_ESI)
        else:
            dp_slope_values_others.append(slope_in_deg)
            dp_elength_values_others.append(dp_row.ELength)
            _compute_statistics(dp_row.ELength, dp_row.Slope, 'ELSEWHERE', count_ESI_ge_HIGH_ESI,
                                count_ESI_lt_HIGH_ESI_ge_MEDIUM_ESI,
                                count_ESI_lt_MEDIUM_ESI_ge_LOW_ESI, count_ESI_lt_LOW_ESI)

        if dp_row.Slope > 0:
            HIGH_ESI_elength_values.append(HIGH_ESI * math.pow(dp_row.Slope, -ALPHA))
            MEDIUM_ESI_elength_values.append(MEDIUM_ESI * math.pow(dp_row.Slope, -ALPHA))
            LOW_ESI_elength_values.append(LOW_ESI * math.pow(dp_row.Slope, -ALPHA))
        else:
            HIGH_ESI_elength_values.append(0)
            MEDIUM_ESI_elength_values.append(0)
            LOW_ESI_elength_values.append(0)
        ESI_slope_values.append(slope_in_deg)

    if conn:
        conn.close()

    # create the plot
    others_points, = plt.semilogy(dp_slope_values_others, dp_elength_values_others, 'r+')
    gully_points, = plt.semilogy(dp_slope_values_gully, dp_elength_values_gully, 'bs')
    landslide_points, = plt.semilogy(dp_slope_values_landslide, dp_elength_values_landslide, 'g^')

    # ESI lines
    plt.semilogy(ESI_slope_values, HIGH_ESI_elength_values)
    plt.semilogy(ESI_slope_values, MEDIUM_ESI_elength_values)
    plt.semilogy(ESI_slope_values, LOW_ESI_elength_values)

    # annotate line HIGH_ESI
    plt.annotate('ESI={}'.format(HIGH_ESI), xy=(ESI_slope_values[-2], HIGH_ESI_elength_values[-2]),
                 xytext=(ESI_slope_values[-2], HIGH_ESI_elength_values[-2]))

    # annotate line MEDIUM_ESI
    plt.annotate('ESI={}'.format(MEDIUM_ESI), xy=(ESI_slope_values[-2], MEDIUM_ESI_elength_values[-2]),
                 xytext=(ESI_slope_values[-2], MEDIUM_ESI_elength_values[-2]))

    # annotate line LOW_ESI
    plt.annotate('ESI={}'.format(LOW_ESI), xy=(ESI_slope_values[-2], LOW_ESI_elength_values[-2]),
                 xytext=(ESI_slope_values[-2], LOW_ESI_elength_values[-2]))

    # add legend to data points
    plt.legend((others_points, gully_points, landslide_points), ('Drain Points', 'Gullies', 'Landslide'),
               loc='upper center', ncol=3)

    # specify axis labels
    plt.ylabel('Effective Length (m)')
    plt.xlabel('Slope (degree)')

    ## specify x-axis range and y-axis range
    # find max y value
    y_max_elength = max(LOW_ESI_elength_values)
    y_max_number_of_digits = int(math.log(y_max_elength, 10)) + 1
    y_max = math.pow(10, y_max_number_of_digits + 1)
    plt.axis([0, 60, 0, y_max])

    # set title for the plot
    plt.title("L-S PLOT")

    # create the statistics table
    col_labels = ['Discharge To', 'ESI >= {}'.format(HIGH_ESI), '{0} > ESI >= {1}'.format(HIGH_ESI, MEDIUM_ESI),
                  '{0} > ESI >= {1}'.format(MEDIUM_ESI, LOW_ESI), 'ESI < {}'.format(LOW_ESI)]

    data_for_gully_row = ['Gully', count_ESI_ge_HIGH_ESI[DRAIN_TYPE.GULLY],
                          count_ESI_lt_HIGH_ESI_ge_MEDIUM_ESI[DRAIN_TYPE.GULLY],
                          count_ESI_lt_MEDIUM_ESI_ge_LOW_ESI[DRAIN_TYPE.GULLY],
                          count_ESI_lt_LOW_ESI[DRAIN_TYPE.GULLY]]
    data_for_landslide_row = ['Landslide', count_ESI_ge_HIGH_ESI[DRAIN_TYPE.LANDSLIDE],
                              count_ESI_lt_MEDIUM_ESI_ge_LOW_ESI[DRAIN_TYPE.LANDSLIDE],
                              count_ESI_lt_HIGH_ESI_ge_MEDIUM_ESI[DRAIN_TYPE.LANDSLIDE],
                              count_ESI_lt_LOW_ESI[DRAIN_TYPE.LANDSLIDE]]
    data_for_elsewhere_row = ['Elsewhere', count_ESI_ge_HIGH_ESI[DRAIN_TYPE.ELSEWHERE],
                              count_ESI_lt_MEDIUM_ESI_ge_LOW_ESI[DRAIN_TYPE.ELSEWHERE],
                              count_ESI_lt_HIGH_ESI_ge_MEDIUM_ESI[DRAIN_TYPE.ELSEWHERE],
                              count_ESI_lt_LOW_ESI[DRAIN_TYPE.ELSEWHERE]]
    table_values=[data_for_gully_row, data_for_landslide_row, data_for_elsewhere_row]

    table = plt.table(cellText=table_values,
                      colWidths=[0.1]*5,
                      rowLabels=None,
                      colLabels=col_labels,
                      loc='bottom',
                      bbox=[0, -0.50, 1, 0.30])   # bbox is : [left, bottom, width, height]

    table.set_fontsize(20)
    table.scale(2, 2)

    # set title for the table
    plt.text(28.0, 0.09, "Statistics", verticalalignment='bottom')
    plt.subplots_adjust(bottom=0.40)

    # make the plot window take full screen size
    figManager = plt.get_current_fig_manager()
    figManager.window.state('zoomed')

    # set title of the plot window
    fig = plt.gcf()
    fig.canvas.set_window_title("L-S Plot")

    plt.show()
    plt.close('all')
    # uncomment this during debugging and put a breakpoint here to see the plot
    #print("Done....")


def _compute_statistics(elength, slope, dp_type, data_dict_ge_HIGH_ESI, data_dict_lt_HIGH_ESI_ge_MEDIUM_ESI,
                        data_dict_lt_MEDIUM_ESI_ge_LOW_ESI, data_dict_lt_LOW_ESI):
    global GULLY
    global LANDSLIDE
    global HIGH_ESI, MEDIUM_ESI, LOW_ESI, ALPHA
    if elength <= 0:
        return
    if elength >= HIGH_ESI * math.pow(slope, -ALPHA):
        if dp_type == GULLY:
            data_dict_ge_HIGH_ESI[DRAIN_TYPE.GULLY] += 1
        elif dp_type == LANDSLIDE:
            data_dict_ge_HIGH_ESI[DRAIN_TYPE.LANDSLIDE] += 1
        else:
            data_dict_ge_HIGH_ESI[DRAIN_TYPE.ELSEWHERE] += 1
    elif elength >= MEDIUM_ESI * math.pow(slope, -ALPHA):
        if dp_type == GULLY:
            data_dict_lt_HIGH_ESI_ge_MEDIUM_ESI[DRAIN_TYPE.GULLY] += 1
        elif dp_type == LANDSLIDE:
            data_dict_lt_HIGH_ESI_ge_MEDIUM_ESI[DRAIN_TYPE.LANDSLIDE] += 1
        else:
            data_dict_lt_HIGH_ESI_ge_MEDIUM_ESI[DRAIN_TYPE.ELSEWHERE] += 1
    elif elength >= LOW_ESI * math.pow(slope, -ALPHA):
        if dp_type == GULLY:
            data_dict_lt_MEDIUM_ESI_ge_LOW_ESI[DRAIN_TYPE.GULLY] += 1
        elif dp_type == LANDSLIDE:
            data_dict_lt_MEDIUM_ESI_ge_LOW_ESI[DRAIN_TYPE.LANDSLIDE] += 1
        else:
            data_dict_lt_MEDIUM_ESI_ge_LOW_ESI[DRAIN_TYPE.ELSEWHERE] += 1
    else:
        if dp_type == GULLY:
             data_dict_lt_LOW_ESI[DRAIN_TYPE.GULLY] += 1
        elif dp_type == LANDSLIDE:
            data_dict_lt_LOW_ESI[DRAIN_TYPE.LANDSLIDE] += 1
        else:
            data_dict_lt_LOW_ESI[DRAIN_TYPE.ELSEWHERE] += 1

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        # This exception occurs when the plot window is closed
        sys.exit(0)
    except Exception as ex:
        if conn:
            conn.close()

        print "Failed to generate L-S Plot."
        print ">>>>>REASON FOR FAILURE:", sys.exc_info()
        print(ex.message)
        sys.exit(1)
    except:
        print "Failed to generate L-S Plot."
        print ">>>>>REASON FOR FAILURE:", sys.exc_info()
        sys.exit(1)
