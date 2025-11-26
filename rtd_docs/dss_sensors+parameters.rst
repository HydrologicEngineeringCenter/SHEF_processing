HEC-DSS Sensor and Parameter Files
==================================

.. toctree::
   :maxdepth: 2
   :caption: Contents

   shefdss_util

.. role:: py(code)
    :language: python

Using sensor and parameter files to store the configuration for translating SHEF text to/from HEC-DSS files was introduced
in HEC's earliest programs for ingesting SHEF text into HEC-DSS. [1]_ As the program was modified and updated over the years,
the sensor and parameter files - with their names and formats - continued unchanged, save for the deprecation of a password field
in the sensor file. [2]_

The :py:`DssLoader` class can still use the traditional columnar format of the sensor and parameter files, but the preferred
format is comma separated values (.csv), which removes the constraints on the lengths of DSS pathname parts they can specify.
Columnar files can be translated into .csv format as described in the :doc:`shefdss_util` page

In the descriptions below, *Fields* refers to the .csv field number, and *cols* refers to the columnar format.

Sensor File
-----------

The sensor file maps SHEF locations and PE codes to DSS time series locations, intervals and descriptions. It controls which
SHEF messages get loaded [3]_ and contains the following information:

    * **Field 1 or cols 1-8 (required)**: The SHEF location identifier
    * **Field 2 or cols 9-10 (required)**: The SHEF PE code
    * **Field 3 or cols 12-15 (optional)**: The DSS time series interval
        Must be one of:
            * Empty: Use irregular interval
            * ``*``: Use interval of SHEF message
            * Format = *nU* (e.g., ``15M``, ``6H``, ``1D``):
                * *n* is a numeric value
                * *U* is one of:
                    * ``M`` - minute(s)
                    * ``H`` - hour(s)
                    * ``D`` - day
                    * ``L`` - month
                    * ``Y`` - year
    * **Field 4 or cols 17-32 (optional)** : The DSS A pathname part
    * **Field 5 or cols 34-49 (required)**: The DSS B pathname part
    * **Field 6 or cols 51-66 (optional)**: The DSS F pathname part

Any sensor file line that begins with ``*`` or at least 10 consecutive spaces is ignored and may be used as a comment line.

Parameter File
--------------

The parameter file maps SHEF PE codes to DSS time series parameters, data types, and units for all locations. It controls value
conversions and contains the following information:

    * **Field 1 or cols 1-2 (required)**: The SHEF PE code
    * **Field 2 or cols 4-28 (optional)**: The DSS C pathname part. If empty, the C part will be the PE code
    * **Field 3 or cols 30-37 (required)**: The DSS data unit
    * **Field 4 or cols 39-46 (required)**: The DSS data type. If ``*``, infer the data type from the SHEF parameter
    * **Field 5 or cols 48-57 (optional)**: The SHEF-to-DSS value conversion. Must be one of:
        * Empty: no conversion (eqivalent to ``1`` or ``1.0``)
        * Numeric value: SHEF value multiplied by this for DSS value
        * ``hm2h``: SHEF value in HHMM converted to decimal hours for DSS value
        * ``dur2h`` (PE codes ``VK``, ``VL``, ``VM``, and ``VR`` only): SHEF value in ``MW<duration>`` converted to ``MWh`` for DSS value

Any parameter file line that begins with ``*`` or at least two consecutive spaces is ignored and may be used as a comment line.

Example Files
-------------

.. dropdown:: Sensor file for single location with multiple parameters

    ::

        * SHEF ID  (required),,,,,
        * PE Code  (required),,,,,
        * Interval (optional),,,,,
        *          blank=irregular,,,,,
        *          * = use SHEF duration,,,,,
        *          nU where n = number and U in (M H D L Y),,,,,
        *              5M = 5Minutes,,,,,
        *              6H = 6Hours,,,,,
        *              1D = 1Day,,,,,
        *              1L = 1Month,,,,,
        *              1Y = 1Year,,,,,
        * A Part (optional) defaults to blank,,,,,
        * B Part (optional) defaults to SHEF ID,,,,,
        * F Part (optional) set to * for forecast time,,,,,
        ***********************************************,,,,,
        * SHEF ID,PE_Code,Interval,A Part,B Part,F Part
        KEYO2,HP,*,,Keystone Lake,From CWMS
        KEYO2,HT,*,,Keystone Lake,From CWMS
        KEYO2,LS,*,,Keystone Lake,From CWMS
        KEYO2,PC,*,,Keystone Lake,From CWMS
        KEYO2,RI,*,,Keystone Lake,From CWMS
        KEYO2,TA,*,,Keystone Lake,From CWMS
        KEYO2,UD,*,,Keystone Lake,From CWMS
        KEYO2,US,*,,Keystone Lake,From CWMS
        KEYO2,VB,*,,Keystone Lake,From CWMS
        KEYO2,XR,*,,Keystone Lake,From CWMS
        KEYO2,YD,*,,Keystone Lake,From CWMS
        KEYO2,YE,*,,Keystone Lake,From CWMS
        KEYO2,YH,*,,Keystone Lake,From CWMS
        KEYO2,YL,*,,Keystone Lake,From CWMS
        KEYO2,YM,*,,Keystone Lake,From CWMS

.. dropdown:: Minimal parameter file for sensor file above

    ::

        * PE code,,,,
        * C Part, (optional),,,
        *     blank = SHEF PE code,,,,
        * Data Unit (required),,,,
        * Data Type (required),,,,
        *     * = infer data type from SHEF parameter,,,,
        * Conversion (optional),,,,
        *     number = numerical factor,,,,
        *     hm2h = hhmm->decimal h,,,,
        *     dur2h = MW<duration> -> MWh for (VK VL VM VR),,,,
        *********************************************************,,,,
        *PE Code,C Part,Data Unit,Data Type,Conversion
        HP,Elev-Pool,ft,*,
        HT,Elev-Tailwater,ft,*,
        LS,Stor-Lake,ac-ft,*,1000
        PC,Precip,in,*,
        RI,Rad-Solar Accumulated,langley,*,
        TA,Temp-Air,F,*,
        UD,Dir-Wind,deg,*,
        US,Speed-Wind,mph,*,
        VB,Volt-Battery,volt,*,
        XR,%-Relative Humidity,%,*,
        YD,Stor-Conservation Pool,ac-ft,*,1000
        YE,Stor-Flood Pool,ac-ft,*,1000
        YH,Volt-Battery Load,volt,*,
        YL,% Conservation Pool Full,%,*,
        YM,% Flood Pool Full,%,*,

.. dropdown:: Parameter file for all standard SHEF PE codes

    ::

        * PE code,,,,
        * C Part, (optional),,,
        *     blank = SHEF PE code,,,,
        * Data Unit (required),,,,
        * Data Type (required),,,,
        *     * = infer data type from SHEF parameter,,,,
        * Conversion (optional),,,,
        *     number = numerical factor,,,,
        *     hm2h = hhmm->decimal h,,,,
        *     dur2h = MW<duration> -> MWh for (VK VL VM VR),,,,
        *********************************************************,,,,
        *PE Code,C Part,Data Unit,Data Type,Conversion
        AD,,,,
        AF,Code-Surface Frost,n/a,*,
        AG,%-Green Vegetation,%,*,
        AM,Code-Surface Dew,n/a,*,
        AT,Timing-Below 25F,hr,*,hm2h
        AU,Timing-Below 32F,hr,*,hm2h
        AW,Timing-Leaf Wetness,hr,*,hm2h

        BA,Depth-Water Equiv Solid,in,*,
        BB,Depth-Heat Deficit,in,*,
        BC,Depth-Liquid Water Stor,in,*,
        BD,Temp-Index,F,*,
        BE,Depth-Max Water Equiv,in,*,
        BF,Depth-Areal Water Equiv,in,*,
        BG,%-Snow Cover-Depl Curve,%,*,
        BH,Depth-Water Equiv Limit,in,*,
        BI,Depth-Excess Liq Wtr Stor,in,*,
        BJ,Depth-Areal Snow Cov Adj,in,*,
        BK,Depth-Lag Exc Wtr Intv 1,in,*,
        BL,Depth-Lag Exc Wtr Intv 2,in,*,
        BM,Depth-Lag Exc Wtr Intv 3,in,*,
        BN,Depth-Lag Exc Wtr Intv 4,in,*,
        BO,Depth-Lag Exc Wtr Intv 5,in,*,
        BP,Depth-Lag Exc Wtr Intv 6,in,*,
        BQ,Depth-Lag Exc Wtr Intv 7,in,*,

        CA,Depth-Upr Zone Tens Wtr,in,*,
        CB,Depth-Upr Zone Free Wtr,in,*,
        CC,Depth-Lwr Zone Tens Wtr,in,*,
        CD,Depth-Sup Lwr Zone Fr Wtr,in,*,
        CE,Depth-Pri Lwr Zone Fr Wtr,in,*,
        CF,Depth-Addl Imperv Area,in,*,
        CG,Depth-Ante Precip Indx,in,*,
        CH,Depth-Soil Moist Indx Def,in,*,
        CI,Depth-Base Flow Stor,in,*,
        CJ,Depth-Base Flow Indx,in,*,
        CK,Depth-Ante Evap Indx Q1,in,*,
        CL,Temp-Ante Index Quad 1,F,*,
        CM,Temp-Frost Index,F,*,
        CN,%-Frost Efficiency Idx,%,*,
        CO,Code-Quadrant 1 Indx Ind,n/a,*,
        CP,Precip-Storm Total,in,*,
        CQ,Precip-Storm Total Runoff,in,*,
        CR,Depth-Ante Indx-Storm,in,*,
        CS,Depth-Ante Indx-Current,in,*,
        CT,Count-Storm Period,unit,*,
        CU,Temp-Air-Aver,F,*,
        CV,Temp-Cur Corrected Synth,F,*,
        CW,Depth-Ante Evap Indx-Stor,in,*,
        CX,Depth-Ante Evap Indx,in,*,
        CY,Depth-Ante Precip Indx,in,*,
        CZ,Code-Climate Index,n/a,*,

        EA,Depth-ET Potential,in,*,
        ED,Depth-Evaopration Pan,in,*,
        EM,Depth-ET,in,*,
        EP,Depth-Evap-Pan,in,*,
        ER,EvapRate,in/day,*,
        ET,Depth-ET-Total,in,*,
        EV,Depth-Evap-Lake,in,*,

        FA,Count-Fish-Shad,unit,*,
        FB,Count-Fish-Sockeye,unit,*,
        FC,Count-Fish-Chinook,unit,*,
        FE,Count-Fish-Cum,unit,*,
        FK,Count-Fish-Coho,unit,*,
        FL,Code-Fish Ladder,n/a,*,
        FP,Count-Fish-Pink,unit,*,
        FS,Count-Fish-Steelhead,unit,*,
        FT,Code-Fish Type,n/a,*,
        FZ,Count-Fish,unit,*,

        GC,Code-Road Surface Cond,n/a,*,
        GD,Depth-Frost Penetration,in,*,
        GL,%-Surface Salt Content,%,*,
        GP,Depth-Frost-Pavement,in,*,
        GR,Code-Frost Report,n/a,*,
        GS,Code-Ground State,n/a,*,
        GT,Depth-Frost-Thawed,in,*,
        GW,Depth-Frost-Pvmt-Thawed,in,*,

        HA,Height,ft,*,
        HB,Depth,ft,*,
        HC,Height-Ceiling,ft,*,
        HD,Height-Head,ft,*,
        HE,Height-Regulating Gate,ft,*,
        HF,Elev-Forebay-Powerhouse,ft,*,
        HG,Stage,ft,*,
        HH,Elev,ft,*,
        HI,Code-Stage Trend Ind,n/a,*,
        HJ,Height-Spillway Gate,ft,*,
        HK,Height-Lake,ft,*,
        HL,Height-Natural Lake,ft,*,
        HM,Height-Tide-MLLW,ft,*,
        HO,Stage-Flood,ft,*,
        HP,Elev-Pool,ft,*,
        HQ,Code-Dist to Edge of Riv,n/a,*,
        HR,Elev-Rule Curve,ft,*,
        HS,Elev-Forebay-Spillway,ft,*,
        HT,Elev-Tailwater,ft,*,
        HU,Stage-Caution,ft,*,
        HV,Depth-Surface Water,in,*,
        HW,Height-Tailwater,ft,*,
        HZ,Elev-Freezing Point,ft,*,1000

        IC,%-Ice Cover,%,*,
        IE,Dist-Ice Extent,mi,*,
        IO,Dist-Open Water Extent,ft,*,
        IR,Code-Ice Report Type,n/a,*,
        IT,Thick-Ice,in,*,

        LA,Area-Lake Surface,acre,*,1000
        LC,Stor-Lake-Delta,ac-ft,*,1000
        LS,Stor-Lake,ac-ft,*,1000

        MD,Code-Dielctric Conststant,n/a,*,
        MI,Depth-Soil Moisture Index,in,*,
        ML,Depth-Lwr Zone Stor Moist,in,*,
        MM,%-Fuel Moisture,%,*,
        MN,Code-Soil Salinity,n/a,*,
        MS,Code-Soil Moisture,n/a,*,
        MT,Temp-Fuel,F,*,
        MU,Depth-Upr Zone Stor Moist,in,*,
        MV,Code-Water Volume,n/a,*,
        MW,%-Soil Moisture,%,*,

        NC,Code-River Control h,n/a,*,
        NG,Opening-Total All Gates,ft,*,
        NL,Count-Flash Boards-Large,unit,*,
        NN,Code-Spillway Gate,n/a,*,
        NO,Code-Gate Opening,n/a,*,
        NS,Count-Flash Boards-Small,unit,*,

        PA,Pres-Atmospheric,in-hg,*,
        PC,Precip,in,*,
        PD,Pres-Atmos-3hr Delta,in-hg,*,
        PE,Code-Characteristic Pres,n/a,*,
        PJ,Precip-Depart From Norm,in,*,
        PL,Pres-Sea Level,in-hg,*,
        PM,Code-Prob of Meas Precip,n/a,*,
        PN,Precip-Normal,in,*,
        PP,Precip-Inc,in,*,
        PR,PrecipRate,in/day,*,
        PT,Code-Precip Type,n/a,*,

        QA,Flow-Adjusted,cfs,*,1000
        QB,Depth-Runoff,in,*,
        QC,Stor-Runoff,ac-ft,*,1000
        QD,Flow-Diversion,cfs,*,1000
        QE,%-Flow Diversion,%,*,
        QF,Speed-Flow,mph,*,
        QG,Flow-Generator,cfs,*,1000
        QI,Flow-In,cfs,*,1000
        QL,Flow-Rule Curve,cfs,*,1000
        QM,Flow-Preproject,cfs,*,1000
        QP,Flow-Pumn,cfs,*,1000
        QR,Flow-River,cfs,*,1000
        QS,Flow-Spillway,cfs,*,1000
        QT,Flow-Total,cfs,*,1000
        QU,Flow-Regulating,cfs,*,1000
        QV,Stor-Inc,ac-ft,*,1000

        RA,%-Albedo Radiation,%,*,
        RI,Rad-Solar Accumulated,langley,*,
        RN,Irrad-Net,W/m2,*,
        RP,%-Solar Radiation,%,*,
        RT,Timing-Solar Rad,hr,*,
        RW,Irrad-Total,W/m2,*,

        SA,%-Snow Cover-Basin,%,*,
        SB,Depth-Blowing Sublimation,in,*,
        SD,Depth-Snow,in,*,
        SE,Temp-Snow Pack,F,*,
        SF,Depth-Snow-Inc,in,*,
        SI,Depth-Snow-On Ice,in,*,
        SL,Elev-Snow Line,ft,*,1000
        SM,Depth-Snow Melt,in,*,
        SP,Depth-Snow Melt+Precip,in,*,
        SR,Code-Snow Report,n/a,*,
        SS,Coeff-Depth of SWE|Snow,n/a,*,
        ST,Code-Snow Temp,n/a,*,
        SU,Depth-Surface Sublimation,in,*,
        SW,Depth-SWE,in,*,

        TA,Temp-Air,F,*,
        TB,Code-Bare Soil Temp,n/a,*,
        TC,Temp-Deg Days-Above 65 F,F,*,
        TD,Temp-Dew Point,F,*,
        TE,Code-Air Temp,n/a,*,
        TF,Temp-Deg Days-Below 32 F,F,*,
        TH,Temp-Deg Days-Below 65 F,F,*,
        TJ,Temp-Depart From Norm,F,*,
        TM,Temp-Air-Wet Bulb,F,*,
        TP,Temp-Pan Water,F,*,
        TS,Temp-Soil-Surface,F,*,
        TV,Code-Vegetated Soil Temp,n/a,*,
        TW,Temp-Water,F,*,
        TZ,Temp-Freezing-Road Surf,F,*,

        UC,Dist-Wind-Cum,mi,*,
        UD,Dir-Wind,deg,*,
        UE,Dir-Wind-Std Dev,deg,*,
        UG,Speed-Wind-Gust,mph,*,
        UH,Dir-Wind-Gust,deg,*,0.1
        UL,Dist-Wind-Inc,mi,*,
        UP,Speed-Wind-Peak,mph,*,
        UQ,Code-Wind Dir and Speed,n/a,*,
        UR,Dir-Wind-Peak,deg,*,0.1
        US,Speed-Wind,mph,*,
        UT,Timing-Wind-Peak,min,*,

        VB,Volt-Battery,volt,*,
        VC,Power-Surplus,MW,*,
        VE,Energy,MWh,*,
        VG,Power-Pumped,MW,*,
        VH,Timing-Power Generation,hr,*,
        VJ,Energy-Pumped,MWh,*,
        VK,Energy-Stor,MWh,*,dur2h
        VL,Energy-Flow,MWh,*,dur2h
        VM,Energy-Loss,MWh,*,dur2h
        VP,Power-Pump Use,MW,*,
        VQ,Energy-Pump Use,MWh,*,
        VR,Energy-Potential,MWh,*,dur2h
        VS,Energy-Station Load,MWh,*,
        VT,Power-Total,MW,*,
        VU,Code-Generator Status,n/a,*,
        VW,Power-Station Load,MW,*,

        WA,Conc-Nitrogen+Argon,ppm,*,
        WC,Cond,umho/cm,*,
        WD,Depth-Water-Piezometer,in,*,
        WG,Pres-Total Dissolved Gas,in-hg,*,
        WH,Conc-Hydrogen Sulfide,ppm,*,
        WL,Conc-Suspended Sediment,ppm,*,
        WO,Conc-Oxygen,ppm,*,
        WP,pH,su,*,
        WS,Conc-Salt,ppt,*,
        WT,Turb,JTU,*,
        WV,Speed-Water,ft/s,*,
        WX,%-Oxygen Saturation,%,*,
        WY,Conc-Chorophyll,ug/l,*,

        XC,%-Sky Cover,%,*,10
        XG,Count-Lightning-Grid Box,unit,*,
        XL,Count-Lightning-Point,unit,*,
        XP,Code-Past NWS Synoptic,n/a,*,
        XR,%-Relative Humidity,%,*,
        XU,Conc-Humidity,g/ft3,*,
        XV,Dist-Visibility,mi,*,
        XW,Code-Curr NWS Synoptic,n/a,*,

        YA,Count-Periods Ab Crit Lvl,unit,*,
        YC,Count-Random Tx,unit,*,
        YF,Power-DCP Forward,W,*,
        YR,Power-DCP Reflected,W,*,
        YS,Count-DCP Tx,unit,*,
        YT,Count-Per Since Rnd Tx,unit,*,
        YV,Volt-Battery 2,volt,*,
        YW,Irrad-Total,W/m2,*,
        YY,Code-Gage Status Lvl 3,n/a,*,


.. [1] The program was a Fortran program named ``SHFDSS`` written in the early to mid 1980s (the documentation for the 10 April 1988
   version provides instructions for updating from versions prior to February, 1986) for the Harris minicomputers that comprised
   USACE's Water Control Data System (WCDS).

.. [2] The default file names (``SHFDSSS`` and ``SHFDSSP`` for the sensor and parameter files, respectively) remained unchanged,
   except for changing to lower-case in the original HEC-DSSVue SHEF import/export code. The columnar formats remain
   unaltered except for the addition of ``hm2h`` and ``dur2h`` parameter file conversions, which were added for the now-obsolete
   :py:`DSSVueLoader` (but remain for use in :py:`DssLoader`). Indeed, you can use :py:`DssLoader` (and thus :py:`DssExporter`) with
   the same filenames and formats.

.. [3] The PE code must be in *both* the sensor and parameter files for a SHEF message with that PE code to be loaded.