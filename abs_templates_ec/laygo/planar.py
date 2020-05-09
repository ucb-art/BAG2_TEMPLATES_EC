# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Dict, Any, List, Tuple, Union

import abc
from collections import namedtuple

from bag import float_to_si_string
# from bag.layout.routing.fill import fill_symmetric_max_density

from .tech import LaygoTech
from ..analog_mos.planar import ExtInfo, RowInfo, EdgeInfo, MOSTechPlanarGeneric

if TYPE_CHECKING:
    from bag.layout.tech import TechInfoConfig
    from bag.layout.routing import WireArray
    from bag.layout.template import TemplateBase

from bag.math import lcm
from bag.layout.util import BBox

FillInfo = namedtuple('FillInfo', ['layer', 'exc_layer', 'x_intv_list', 'y_intv_list'])


class LaygoTechPlanarBase(MOSTechPlanarGeneric, LaygoTech, metaclass=abc.ABCMeta):
    """Base class for implementations of LaygoTech in Finfet technologies.

    This class for now handles all DRC rules and drawings related to PO, OD, CPO,
    and MD. The rest needs to be implemented by subclasses.

    Parameters
    ----------
    config : Dict[str, Any]
        the technology configuration dictionary.
    tech_info : TechInfo
        the TechInfo object.
    mos_entry_name : str
        name of the entry that contains technology parameters for transistors in
        the given configuration dictionary.
    """

    def __init__(self, config, tech_info, mos_entry_name='mos'):
        # type: (Dict[str, Any], TechInfoConfig, str) -> None
        LaygoTech.__init__(self, config, tech_info, mos_entry_name=mos_entry_name)

    def get_laygo_row_yloc_info(self, lch_unit, w, is_sub, **kwargs):
        # type: (int, int, bool, **Any) -> Dict[str, Any]
        mos_constants = self.get_mos_tech_constants(lch_unit)
        od_spy = mos_constants['od_spy']
        po_spy = mos_constants['po_spy']

        g_conn_info = self.get_conn_drc_info(lch_unit, 'g', is_laygo=True)
        g_m1_sple = g_conn_info[1]['sp_le']

        if is_sub:
            yloc_info = self.get_sub_yloc_info(lch_unit, w, **kwargs)
        else:
            yloc_info = self.get_mos_yloc_info(lch_unit, w, **kwargs)

        blk_yb, blk_yt = blk_y = yloc_info['blk']
        po_yb, po_yt = po_y = yloc_info['po']
        od_yb, od_yt = od_y = yloc_info['od']

        # get wire coordinates
        conn_yloc_info = self.get_laygo_conn_yloc_info(lch_unit, od_y, is_sub)
        d_yb, d_yt = d_y = conn_yloc_info['d_y']
        g_yb, g_yt = g_y = conn_yloc_info['g_y']

        # step 2: compute top CPO location.
        return dict(
            blk=blk_y,
            po=po_y,
            od=od_y,
            top_margins=dict(
                od=(blk_yt - od_yt, od_spy),
                po=(blk_yt - po_yt, po_spy),
                m1=(blk_yt - d_yt, g_m1_sple),
            ),
            bot_margins=dict(
                od=(od_yb - blk_yb, od_spy),
                po=(blk_yt - po_yt, po_spy),
                m1=(g_yb - blk_yb, g_m1_sple),
            ),
            fill_info={},
            g_conn_y=g_y,
            gb_conn_y=d_y,
            ds_conn_y=d_y,
        )

    @abc.abstractmethod
    def get_laygo_conn_yloc_info(self, lch_unit, od_y, is_sub):
        # type: (int, Tuple[int, int], bool) -> Dict[str, Any]
        """Computes Y coordinates of various metal layers in the laygo block.

        The returned dictionary should have the following entries:

        g_y :
            a tuple of gate metal Y coordinates.
        d_y :
            a tuple of drain metal Y coordinates.
        """
        return {}

    @abc.abstractmethod
    def get_laygo_blk_yloc_info(self, w, blk_type, row_info, **kwargs):
        # type: (int, str, Dict[str, Any], **Any) -> Dict[str, Any]
        """Computes Y coordinates of various layers in the laygo block.

        The returned dictionary should have the following entries:

        od :
            a tuple of OD bottom/top Y coordinates.
        md :
            a tuple of MD bottom/top Y coordinates.
        """
        return {}

    @abc.abstractmethod
    def draw_laygo_g_connection(self, template, mos_info, g_loc, num_fg, **kwargs):
        # type: (TemplateBase, Dict[str, Any], str, int, **Any) -> List[WireArray]
        """Draw laygo gate connections.

        Parameters
        ----------
        template : TemplateBase
            the TemplateBase object to draw layout in.
        mos_info : Dict[str, Any]
            the block layout information dictionary.
        g_loc : str
            gate wire alignment location.  Either 'd' or 's'.
        num_fg : int
            number of gate fingers.
        **kwargs :
            optional parameters.

        Returns
        -------
        warr_list : List[WireArray]
            list of port wires as single-wire WireArrays.
        """
        return []

    @abc.abstractmethod
    def draw_laygo_ds_connection(self, template, mos_info, tidx_list, ds_code, **kwargs):
        # type: (TemplateBase, Dict[str, Any], List[Union[float, int]], int, **Any) -> List[WireArray]
        """Draw laygo drain/source connections.

        Parameters
        ----------
        template : TemplateBase
            the TemplateBase object to draw layout in.
        mos_info : Dict[str, Any]
            the block layout information dictionary.
        tidx_list : List[Union[float, int]]
            list of track index to draw drain/source wires.
        ds_code : int
        **kwargs :
            optional parameters.

        Returns
        -------
        warr_list : List[WireArray]
            list of port wires as single-wire WireArrays.
        """
        return []

    @abc.abstractmethod
    def draw_laygo_sub_connection(self, template, mos_info, **kwargs):
        # type: (TemplateBase, Dict[str, Any], **Any) -> List[WireArray]
        """Draw laygo substrate connections.

        Parameters
        ----------
        template : TemplateBase
            the TemplateBase object to draw layout in.
        mos_info : Dict[str, Any]
            the block layout information dictionary.
        **kwargs :
            optional parameters.

        Returns
        -------
        warr_list : List[WireArray]
            list of port wires as single-wire WireArrays.
        """
        return []

    def get_default_end_info(self):
        # type: () -> Any
        return EdgeInfo(od_type=None, draw_layers={}, y_intv={}), []

    def get_laygo_mos_row_info(self,  # type: LaygoTechPlanarBase
                               lch_unit,  # type: int
                               w_max,  # type: int
                               w_sub,  # type: int
                               mos_type,  # type: str
                               threshold,  # type: str
                               bot_row_type,  # type: str
                               top_row_type,  # type: str
                               **kwargs):
        # type: (...) -> Dict[str, Any]

        # figure out various properties of the current laygo block
        is_sub = (mos_type == 'ptap' or mos_type == 'ntap')
        sub_type = 'ptap' if mos_type == 'nch' or mos_type == 'ptap' else 'ntap'

        # get Y coordinate information dictionary
        row_yloc_info = self.get_laygo_row_yloc_info(lch_unit, w_max, is_sub, **kwargs)
        blk_yb, blk_yt = row_yloc_info['blk']
        po_yloc = row_yloc_info['po']
        od_yloc = row_yloc_info['od']
        # md_yloc = row_yloc_info['md']
        top_margins = row_yloc_info['top_margins']
        bot_margins = row_yloc_info['bot_margins']
        fill_info = row_yloc_info['fill_info']
        g_conn_y = row_yloc_info['g_conn_y']
        gb_conn_y = row_yloc_info['gb_conn_y']
        ds_conn_y = row_yloc_info['ds_conn_y']

        mos_constants = self.get_mos_tech_constants(lch_unit)
        imp_min_h = mos_constants.get('imp_min_h', 0)

        # compute extension information
        mtype = (mos_type, mos_type)
        po_type = 'PO_sub' if is_sub else 'PO'
        po_types = (po_type, po_type)
        lr_edge_info = EdgeInfo(od_type='sub' if is_sub else 'mos', draw_layers={}, y_intv={})
        ext_top_info = ExtInfo(margins=top_margins,
                               od_h=row_yloc_info['od'][1] - row_yloc_info['od'][0],
                               imp_min_h=imp_min_h,
                               mtype=mtype,
                               m1_sub_h=0,
                               thres=threshold,
                               po_types=po_types,
                               edgel_info=lr_edge_info,
                               edger_info=lr_edge_info,
                               )
        ext_bot_info = ExtInfo(margins=bot_margins,
                               od_h=row_yloc_info['od'][1] - row_yloc_info['od'][0],
                               imp_min_h=imp_min_h,
                               mtype=mtype,
                               m1_sub_h=0,
                               thres=threshold,
                               po_types=po_types,
                               edgel_info=lr_edge_info,
                               edger_info=lr_edge_info,
                               )

        lay_info_list = [(lay, 0, blk_yb, blk_yt)
                         for lay in self.get_mos_layers(mos_type, threshold)]
        imp_params = [(mos_type, threshold, blk_yb, blk_yt, blk_yb, blk_yt)],

        fill_info_list = [FillInfo(layer=layer, exc_layer=info[0], x_intv_list=[],
                                   y_intv_list=info[1]) for layer, info in fill_info.items()]

        blk_y = (blk_yb, blk_yt)
        lch = lch_unit * self.res * self.tech_info.layout_unit
        lch_str = float_to_si_string(lch)
        row_name_id = '%s_l%s_w%d_%s' % (mos_type, lch_str, w_max, threshold)
        return dict(
            w_max=w_max,
            w_sub=w_sub,
            lch_unit=lch_unit,
            row_type=mos_type,
            sub_type=sub_type,
            threshold=threshold,
            arr_y=blk_y,
            od_y=od_yloc,
            po_y=po_yloc,
            # md_y=md_yloc,
            ext_top_info=ext_top_info,
            ext_bot_info=ext_bot_info,
            lay_info_list=lay_info_list,
            imp_params=imp_params,
            fill_info_list=fill_info_list,
            g_conn_y=g_conn_y,
            gb_conn_y=gb_conn_y,
            ds_conn_y=ds_conn_y,
            row_name_id=row_name_id,
        )

    def get_laygo_sub_row_info(self, lch_unit, w, mos_type, threshold, **kwargs):
        # type: (int, int, str, str, **Any) -> Dict[str, Any]
        return self.get_laygo_mos_row_info(lch_unit, w, w, mos_type, threshold, '', '', **kwargs)

    def get_laygo_blk_info(self, blk_type, w, row_info, **kwargs):
        # type: (str, int, Dict[str, Any], **Any) -> Dict[str, Any]

        arr_y = row_info['arr_y']
        po_y = row_info['po_y']
        lch_unit = row_info['lch_unit']
        row_type = row_info['row_type']
        sub_type = row_info['sub_type']
        threshold = row_info['threshold']
        row_ext_top = row_info['ext_top_info']
        row_ext_bot = row_info['ext_bot_info']
        lay_info_list = row_info['lay_info_list']
        imp_params = row_info['imp_params']

        mos_constants = self.get_mos_tech_constants(lch_unit)
        sd_pitch = mos_constants['sd_pitch']

        # get Y coordinate information dictionary
        yloc_info = self.get_laygo_blk_yloc_info(w, blk_type, row_info, **kwargs)
        od_yloc = yloc_info['od']
        # md_yloc = yloc_info['md']

        # figure out various properties of the current laygo block
        is_sub = (row_type == sub_type)
        
        y_intv = dict(od=od_yloc, 
                      # md=md_yloc,
                      )

        if blk_type.startswith('fg1'):
            mtype = (row_type, row_type)
            od_type = 'mos'
            fg = 1
            od_intv = (0, 1)
            edgel_info = edger_info = EdgeInfo(od_type=od_type, draw_layers={}, y_intv=y_intv)
            po_types = ('PO',)
        elif blk_type == 'sub':
            # deletes poly in sub tap cell because i dont want to complicate PM doping layer setup
            po_y = (0, 0)
            
            mtype = (sub_type, row_type)
            od_type = 'sub'
            if is_sub:
                fg = 2
                od_intv = (0, 2)
                edgel_info = edger_info = EdgeInfo(od_type=od_type, draw_layers={}, y_intv=y_intv)
                po_types = ('PO_sub', 'PO_sub')
            else:
                mos_constants = self.get_mos_tech_constants(lch_unit)
                imp_od_ency = mos_constants['imp_od_ency']
                imp_yb = od_yloc[0] - imp_od_ency
                imp_yt = od_yloc[1] + imp_od_ency
                arr_yb, arr_yt = arr_y
                if kwargs.get('imp_min_g', False):
                    row_yb = arr_yb
                    row_yt = max(imp_yb, arr_yb)
                    sub_yb = row_yt
                    sub_yt = arr_yt
                elif kwargs.get('imp_min_d', False):
                    sub_yb = arr_yb
                    sub_yt = min(imp_yt, arr_yt)
                    row_yb = sub_yt
                    row_yt = arr_yt
                else:
                    row_yb = row_yt = arr_yb
                    sub_yb = arr_yb
                    sub_yt = arr_yt
                lay_info_list = [(lay, 0, sub_yb, sub_yt)
                                 for lay in self.get_mos_layers(sub_type, threshold)]
                if row_yt > row_yb:
                    lay_info_list.extend((lay, 0, row_yb, row_yt)
                                         for lay in self.get_mos_layers(row_type, threshold))
                fg = self.get_sub_columns(lch_unit)
                od_intv = (2, fg - 2)
                edgel_info = edger_info = EdgeInfo(od_type=None, draw_layers={}, y_intv=y_intv)
                po_types = ('PO_dummy', 'PO_edge_sub') + ('PO_sub',) * (fg - 4) + \
                           ('PO_edge_sub', 'PO_dummy',)
        else:
            mtype = (row_type, row_type)
            od_type = 'mos'
            fg = 2
            od_intv = (0, 2)
            edgel_info = edger_info = EdgeInfo(od_type=od_type, draw_layers={}, y_intv=y_intv)
            po_types = ('PO', 'PO')

        # update extension information
        # noinspection PyProtectedMember
        ext_top_info = row_ext_top._replace(mtype=mtype, po_types=po_types,
                                            edgel_info=edgel_info, edger_info=edger_info)
        # noinspection PyProtectedMember
        ext_bot_info = row_ext_bot._replace(mtype=mtype, po_types=po_types,
                                            edgel_info=edgel_info, edger_info=edger_info)

        layout_info = dict(
            is_sub_row=is_sub,
            blk_type='sub' if is_sub else 'mos',
            lch_unit=lch_unit,
            fg=fg,
            arr_y=arr_y,
            draw_od=True,
            sd_pitch=sd_pitch,
            row_info_list=[RowInfo(od_x=od_intv,
                                   od_y=od_yloc,
                                   od_type=(od_type, sub_type),
                                   po_y=po_y,
                                   ), ],
            sub_y_list=[od_yloc, row_info['ds_conn_y'], row_info['ds_conn_y']],
                               
            lay_info_list=lay_info_list,
            sub_type=sub_type,
            imp_params=imp_params,
            is_sub_ring=False,
            dnw_mode='',
        )

        # step 8: return results
        return dict(
            layout_info=layout_info,
            ext_top_info=ext_top_info,
            ext_bot_info=ext_bot_info,
            left_edge_info=(edgel_info, []),
            right_edge_info=(edger_info, []),
        )

    def get_laygo_end_info(self, lch_unit, mos_type, threshold, fg, is_end, blk_pitch, **kwargs):
        # type: (int, str, str, int, bool, int, **Any) -> Dict[str, Any]
        return self.get_analog_end_info(lch_unit, mos_type, threshold, fg, is_end,
                                        blk_pitch, **kwargs)

    def get_laygo_space_info(self, row_info, num_blk, left_blk_info, right_blk_info):
        # type: (Dict[str, Any], int, Any, Any) -> Dict[str, Any]

        od_y = row_info['od_y']
        po_y = row_info['po_y']
        # md_y = row_info['md_y']
        arr_y = row_info['arr_y']
        lch_unit = row_info['lch_unit']
        row_type = row_info['row_type']
        sub_type = row_info['sub_type']
        row_ext_top = row_info['ext_top_info']
        row_ext_bot = row_info['ext_bot_info']
        lay_info_list = row_info['lay_info_list']
        imp_params = row_info['imp_params']

        is_sub = (row_type == sub_type)

        mos_constants = self.get_mos_tech_constants(lch_unit)
        sd_pitch = mos_constants['sd_pitch']
        od_fill_w_max = None
        
        # TODO
        # This probably needs to come from get_mos_tech_constants,
        # but its not super sensitive because of the // done in od_spx_fg
        # this works for now
        od_spx = lch_unit

        od_spx_fg = -(-(od_spx - sd_pitch + lch_unit) // sd_pitch) + 2
        
        # get OD fill X interval
        area = num_blk - 2 * od_spx_fg
        if area > 0:
            if od_fill_w_max is None:
                # od_x_list = [(od_spx_fg, num_blk - od_spx_fg)]
                od_x = (od_spx_fg, num_blk - od_spx_fg)
            else:
                raise Exception('Greg is not rewriting planar to accommodate od_list')
                # od_fg_max = (od_fill_w_max - lch_unit) // sd_pitch - 1
                # od_x_list = fill_symmetric_max_density(area, area, 2, od_fg_max, od_spx_fg,
                #                                        offset=od_spx_fg, fill_on_edge=True,
                #                                        cyclic=False)[0]
            draw_od = True
        else:
            # This is just a reasonable dummy value since draw_od is false
            od_x = (1, 2)
            draw_od = False

        row_info_list = [RowInfo(od_x=od_x, od_y=od_y, od_type=('dum', sub_type),
                                 po_y=po_y), ]

        # update extension information
        cur_edge_info = EdgeInfo(od_type=None, draw_layers={}, y_intv=dict(od=od_y))
        # figure out poly types per finger
        po_types = []
        od_intv_idx = 0
        for cur_idx in range(num_blk):
            if cur_idx == 0 or cur_idx == num_blk - 1:
                od_type = left_blk_info[0].od_type if cur_idx == 0 else right_blk_info[0].od_type
                if od_type == 'mos':
                    po_types.append('PO_edge')
                elif od_type == 'sub':
                    po_types.append('PO_edge_sub')
                elif od_type == 'dum':
                    po_types.append('PO_edge_dummy')
                else:
                    po_types.append('PO_dummy')
            elif cur_idx < od_spx_fg or cur_idx >= num_blk - od_spx_fg:
                po_types.append('PO_dummy')

            # elif od_intv_idx < len(od_x_list):
            elif od_intv_idx < 1:
                # cur_od_intv = od_x_list[od_intv_idx]
                cur_od_intv = od_x
                if cur_od_intv[1] == cur_idx:
                    po_types.append('PO_edge_dummy')
                    od_intv_idx += 1
                elif cur_od_intv[0] <= cur_idx < cur_od_intv[1]:
                    po_types.append('PO_gate_dummy')
                elif cur_idx == cur_od_intv[0] - 1:
                    po_types.append('PO_edge_dummy')
                else:
                    if cur_idx > cur_od_intv[1]:
                        od_intv_idx += 1
                    po_types.append('PO_dummy')
            else:
                po_types.append('PO_dummy')

        # noinspection PyProtectedMember
        ext_top_info = row_ext_top._replace(po_types=po_types, edgel_info=cur_edge_info,
                                            edger_info=cur_edge_info)
        # noinspection PyProtectedMember
        ext_bot_info = row_ext_bot._replace(po_types=po_types, edgel_info=cur_edge_info,
                                            edger_info=cur_edge_info)

        lr_edge_info = (cur_edge_info, [])
        layout_info = dict(
            is_sub_row=is_sub,
            blk_type='sub' if is_sub else 'mos',
            lch_unit=lch_unit,
            sd_pitch=sd_pitch,
            fg=num_blk,
            arr_y=arr_y,
            draw_od=draw_od,
            row_info_list=row_info_list,
            sub_y_list=[od_y, row_info['ds_conn_y'], row_info['ds_conn_y']],
            lay_info_list=lay_info_list,
            sub_type=sub_type,
            imp_params=imp_params,
            is_sub_ring=False,
            dnw_mode='',
        )

        # step 8: return results
        return dict(
            layout_info=layout_info,
            ext_top_info=ext_top_info,
            ext_bot_info=ext_bot_info,
            left_edge_info=lr_edge_info,
            right_edge_info=lr_edge_info,
        )

    def get_row_extension_info(self,  # type: LaygoTechPlanarBase
                               bot_ext_list,  # type: List[Union[int, ExtInfo]]
                               top_ext_list,  # type: List[Union[int, ExtInfo]]
                               ):
        # type: (...) -> List[Tuple[int, int, ExtInfo, ExtInfo]]
        # merge list of bottom and top extension informations into a list of
        # bottom/top extension tuples
        bot_idx = top_idx = 0
        bot_len = len(bot_ext_list)
        top_len = len(top_ext_list)
        ext_groups = []
        cur_fg = bot_off = top_off = 0
        while bot_idx < bot_len and top_idx < top_len:
            bot_info = bot_ext_list[bot_idx]  # type: Union[int, ExtInfo]
            top_info = top_ext_list[top_idx]  # type: Union[int, ExtInfo]
            if isinstance(bot_info, int) and isinstance(top_info, int):
                cur_fg += bot_info
                bot_off = top_off = cur_fg
                bot_idx += 1
                top_idx += 1
            else:
                bot_ptype = bot_info.po_types
                top_ptype = top_info.po_types
                bot_stop = bot_off + len(bot_ptype)
                top_stop = top_off + len(top_ptype)
                stop_idx = min(bot_stop, top_stop)

                # create new bottom/top extension information objects for the
                # current overlapping block
                bot_po_types = bot_ptype[cur_fg - bot_off:stop_idx - bot_off]
                top_po_types = top_ptype[cur_fg - top_off:stop_idx - top_off]
                # noinspection PyProtectedMember
                cur_bot_info = bot_info._replace(po_types=bot_po_types)
                # noinspection PyProtectedMember
                cur_top_info = top_info._replace(po_types=top_po_types)
                # append tuples of current number of fingers and bottom/top
                # extension information object
                ext_groups.append((cur_fg, stop_idx - cur_fg, cur_bot_info, cur_top_info))

                cur_fg = stop_idx
                if stop_idx == bot_stop:
                    bot_off = cur_fg
                    bot_idx += 1
                if stop_idx == top_stop:
                    top_off = cur_fg
                    top_idx += 1

        return ext_groups

    def draw_laygo_connection(self, template, mos_info, blk_type, options):
        # type: (TemplateBase, Dict[str, Any], str, Dict[str, Any]) -> None

        layout_info = mos_info['layout_info']
        sub_type = layout_info['sub_type']

        if blk_type in ('fg2d', 'fg2s', 'stack2d', 'stack2s', 'fg1d', 'fg1s'):
            g_loc = blk_type[-1]
            num_fg = int(blk_type[-2])
            if blk_type.startswith('fg2'):
                didx_list = [0.5]
                sidx_list = [-0.5, 1.5]
            elif blk_type.startswith('stack2'):
                didx_list = [1.5]
                sidx_list = [-0.5]
            else:
                didx_list = [0.5]
                sidx_list = [-0.5]
            g_warrs = self.draw_laygo_g_connection(template, mos_info, g_loc, num_fg, **options)
            d_warrs = self.draw_laygo_ds_connection(template, mos_info, didx_list, ds_code=2, **options)
            s_warrs = self.draw_laygo_ds_connection(template, mos_info, sidx_list, ds_code=1, **options)

            for name, warr_list in (('g', g_warrs), ('d', d_warrs), ('s', s_warrs)):
                template.add_pin(name, warr_list, show=False)
                if len(warr_list) > 1:
                    for idx, warr in enumerate(warr_list):
                        template.add_pin('%s%d' % (name, idx), warr, show=False)
        elif blk_type == 'sub':
            warrs = self.draw_laygo_sub_connection(template, mos_info, **options)
            port_name = 'VDD' if sub_type == 'ntap' else 'VSS'
            s_warrs = warrs[0::1]
            d_warrs = warrs[0::1]
            template.add_pin(port_name, s_warrs, show=False)
            template.add_pin(port_name + '_s', s_warrs, show=False)
            template.add_pin(port_name + '_d', d_warrs, show=False)

        else:
            raise ValueError('Unsupported laygo primitive type: %s' % blk_type)


class LaygoTechPlanarGeneric(LaygoTechPlanarBase):
    def __init__(self, config, tech_info, mos_entry_name='mos'):
        # type: (Dict[str, Any], TechInfoConfig, str) -> None
        MOSTechPlanarGeneric.__init__(self, config, tech_info, mos_entry_name=mos_entry_name)

    def get_laygo_conn_yloc_info(self, lch_unit, od_y, is_sub):
        # type: (int, Tuple[int, int], bool) -> Dict[str, Any]
        mos_constants = self.get_mos_tech_constants(lch_unit)

        m1_gd_sp = mos_constants['m1_gd_spy']

        g_conn_info = self.get_conn_drc_info(lch_unit, 'g', is_laygo=True)
        d_conn_info = self.get_conn_drc_info(lch_unit, 'd', is_laygo=True)

        d_m1_top_exty = d_conn_info[1]['top_ext']
        d_m1_bot_exty = d_conn_info[1]['bot_ext']

        # compute gate/drain connection parameters
        g_m1_h = g_conn_info[1]['min_len']

        od_yb, od_yt = od_y

        if is_sub:
            d_m1_yb = od_y[0]
            d_m1_yt = od_y[1] 
            g_m1_yb = d_m1_yb
            g_m1_yt = d_m1_yt

        else:
            d_m1_yb = od_yb - d_m1_bot_exty
            d_m1_yt = max(od_yt + d_m1_top_exty, d_m1_yb + d_conn_info[1]['min_len'])
            
            g_m1_yt = d_m1_yb - m1_gd_sp
            g_m1_yb = g_m1_yt - g_m1_h

        return dict(
            g_y=(g_m1_yb, g_m1_yt),
            d_y=(d_m1_yb, d_m1_yt),
        )

    def get_laygo_row_yloc_info(self, lch_unit, w, is_sub, **kwargs):
        # type: (int, int, bool, **Any) -> Dict[str, Any]

        if is_sub:
            yloc_info = self.get_laygo_sub_yloc_info(lch_unit, w, **kwargs)
        else:
            yloc_info = self.get_laygo_mos_yloc_info(lch_unit, w, **kwargs)

        blk_y = yloc_info['blk']
        po_y = yloc_info['po']
        od_y = yloc_info['od']
        top_margins = yloc_info['top_margins']
        bot_margins = yloc_info['bot_margins']
        
        # get wire coordinates
        conn_yloc_info = self.get_laygo_conn_yloc_info(lch_unit, od_y, is_sub)
        d_y = conn_yloc_info['d_y']
        g_y = conn_yloc_info['g_y']

        # step 2: compute top CPO location.
        return dict(
            blk=blk_y,
            po=po_y,
            od=od_y,
            
            top_margins=top_margins,
            bot_margins=bot_margins,
            
            fill_info={},
            g_conn_y=g_y,
            gb_conn_y=d_y,
            ds_conn_y=d_y,
        )

    def get_laygo_blk_yloc_info(self, w, blk_type, row_info, **kwargs):
        # type: (int, str, Dict[str, Any], **Any) -> Dict[str, Any]
        imp_min_g = kwargs.get('imp_min_g', False)

        lch_unit = row_info['lch_unit']
        od_yb, od_yt = row_info['od_y']

        mos_constants = self.get_mos_tech_constants(lch_unit)
        fin_p = mos_constants['mos_pitch']

        od_h = int(round(w / self.tech_info.layout_unit / self.tech_info.resolution)) // fin_p * fin_p

        if imp_min_g and blk_type == 'sub':
            od_y = (od_yt - od_h, od_yt)
        else:
            od_y = (od_yb, od_yb + od_h)

        return dict(
            od=od_y,
        )

    def draw_laygo_space_connection(self, template, space_info, left_blk_info, right_blk_info):
        # type: (TemplateBase, Dict[str, Any], Any, Any) -> None
        pass

    def _draw_g_via(self, template, lch_unit, m1_yb, m1_yt, x_list, r_list, l_list):
        mos_lay_table = self.config['mos_layer_table']
        via_table = self.config['via_id']
        layer_table = self.config['layer_name']

        mos_constants = self.get_mos_tech_constants(lch_unit)
        sd_pitch = mos_constants['sd_pitch']
        g_via_info = mos_constants['laygo_g_via']

        g_v0_w, g_v0_h = g_via_info['dim'][0]
        
        g_m1_h = g_v0_h + 2*g_via_info['top_enc_le'][0]
        g_m1_yb = m1_yt - g_m1_h
        g_m1_yc = (g_m1_yb + m1_yt) // 2

        bot_encx = g_via_info['bot_enc_side'][0]
        bot_ency = g_via_info['bot_enc_le'][0]
        top_encx = g_via_info['top_enc_side'][0]
        top_ency = g_via_info['top_enc_le'][0]

        enc1 = [bot_encx, bot_encx, bot_ency, bot_ency]
        enc2 = [top_encx, top_encx, top_ency, top_ency]

        conn_layer = self.get_dig_conn_layer()
        via_id = via_table[(mos_lay_table['PO'], layer_table[conn_layer])]

        for xc, rflag, lflag in zip(x_list, r_list, l_list):
            if rflag:
                template.add_via_primitive(via_id, [xc + sd_pitch//2, g_m1_yc], enc1=enc1, enc2=enc2, unit_mode=True)
                template.add_rect(('M1', 'drawing'), BBox(xc, g_m1_yb, xc + sd_pitch // 2 + g_v0_w // 2 + top_encx,
                                                          m1_yt, self.res, unit_mode=True))

            if lflag:
                template.add_via_primitive(via_id, [xc - sd_pitch//2, g_m1_yc], enc1=enc1, enc2=enc2, unit_mode=True)
                template.add_rect(('M1', 'drawing'), BBox(xc - sd_pitch // 2 - g_v0_w // 2 - top_encx, g_m1_yb, xc,
                                                          m1_yt, self.res, unit_mode=True))

    def _draw_ds_via(self, template, lch_unit, od_yb, od_yt, x_list):
        mos_lay_table = self.config['mos_layer_table']
        via_table = self.config['via_id']
        layer_table = self.config['layer_name']
        mos_constants = self.get_mos_tech_constants(lch_unit)

        d_conn_w = mos_constants['laygo_d_conn_w'][0]
        d_via_info = mos_constants['laygo_d_via']

        w_unit = od_yt - od_yb

        # get number of vias
        d_v0_h = d_via_info['dim'][0][1]
        d_v0_w = d_via_info['dim'][0][0]
        d_v0_sp = d_via_info['sp'][0]
        d_v0_od_ency = d_via_info['bot_enc_le'][0]
        d_v0_n = (w_unit - 2 * d_v0_od_ency + d_v0_sp) // (d_v0_h + d_v0_sp)
        d_v0_arrh = d_v0_n * (d_v0_h + d_v0_sp) - d_v0_sp
        
        bot_encx = (d_conn_w - d_v0_w) // 2
        top_encx = (d_conn_w - d_v0_w) // 2
        bot_ency = d_via_info['bot_enc_le'][0]
        top_ency = d_via_info['top_enc_le'][0]
        enc1 = [bot_encx, bot_encx, bot_ency, bot_ency]
        enc2 = [top_encx, top_encx, top_ency, top_ency]

        conn_layer = self.get_dig_conn_layer()
        via_id = via_table[(mos_lay_table['OD'], layer_table[conn_layer])]

        for xc in x_list:
            template.add_via_primitive(via_id, [xc, od_yb + w_unit // 2], enc1=enc1, enc2=enc2,
                                       num_rows=d_v0_n, sp_rows=d_v0_sp, unit_mode=True)

    def draw_laygo_g_connection(self, template, mos_info, g_loc, num_fg, **kwargs):
        # type: (TemplateBase, Dict[str, Any], str, int, **Any) -> List[WireArray]
        layout_info = mos_info['layout_info']
        lch_unit = layout_info['lch_unit']
        od_y = layout_info['row_info_list'][0].od_y

        mos_constants = self.get_mos_tech_constants(lch_unit)
        sd_pitch = mos_constants['sd_pitch']

        conn_yloc_info = self.get_laygo_conn_yloc_info(lch_unit, od_y, False)
        m1_yb, m1_yt = conn_yloc_info['g_y']

        if g_loc == 'd':
            x_list = [sd_pitch]
            l_list = [True]
            if num_fg > 1:
                r_list = [True]
            else:
                r_list = [False]
        elif num_fg == 1:
            x_list = [0]
            r_list = [True]
            l_list = [False]
        else:
            x_list = [0, 2 * sd_pitch]
            r_list = [True, False]
            l_list = [False, True]
       
        self._draw_g_via(template, lch_unit, m1_yb, m1_yt, x_list, r_list, l_list)

        conn_layer = self.get_dig_conn_layer()
        warrs = []
        for xc in x_list:
            tr_idx = template.grid.coord_to_track(conn_layer, xc, unit_mode=True)
            warrs.append(template.add_wires(conn_layer, tr_idx, m1_yb, m1_yt, unit_mode=True))

        return warrs

    def draw_laygo_ds_connection(self, template, mos_info, tidx_list, **kwargs):
        # type: (TemplateBase, Dict[str, Any], List[Union[float, int]], **Any) -> List[WireArray]
        layout_info = mos_info['layout_info']
        lch_unit = layout_info['lch_unit']
        od_y = layout_info['row_info_list'][0].od_y

        conn_yloc_info = self.get_laygo_conn_yloc_info(lch_unit, od_y, False)
        m1_yb, m1_yt = conn_yloc_info['d_y']

        conn_layer = self.get_dig_conn_layer()
        x_list = [template.grid.track_to_coord(conn_layer, tr_idx, unit_mode=True)
                  for tr_idx in tidx_list]
                       
        self._draw_ds_via(template, lch_unit, od_y[0], od_y[1], x_list)

        warrs = []
        for tr_idx in tidx_list:
            warrs.append(template.add_wires(conn_layer, tr_idx, m1_yb, m1_yt, unit_mode=True))
        return warrs

    def draw_laygo_sub_connection(self, template, mos_info, **kwargs):
        # type: (TemplateBase, Dict[str, Any], **Any) -> List[WireArray]
        layout_info = mos_info['layout_info']
        is_sub_row = layout_info['is_sub_row']
        lch_unit = layout_info['lch_unit']
        od_y = layout_info['row_info_list'][0].od_y

        mos_constants = self.get_mos_tech_constants(lch_unit)
        sd_pitch = mos_constants['sd_pitch']

        conn_yloc_info = self.get_laygo_conn_yloc_info(lch_unit, od_y, is_sub_row)
        d_m1_yt = conn_yloc_info['d_y'][1]
        d_m1_yb = conn_yloc_info['d_y'][0]

        # get X coordinates list
        if is_sub_row:
            # we know this has to be two fingers
            xoff = 0
            num_col = 2
        else:
            idx_list = self.get_sub_port_columns(lch_unit)
            xoff = sd_pitch * idx_list[0]
            num_col = len(idx_list)
        x_list = list(range(xoff, xoff + (num_col + 1) * sd_pitch, sd_pitch))

        self._draw_ds_via(template, lch_unit, od_y[0], od_y[1], x_list)

        warrs = []
        conn_layer = self.get_dig_conn_layer()
        for xc in x_list:
            tr_idx = template.grid.coord_to_track(conn_layer, xc, unit_mode=True)
            warrs.append(template.add_wires(conn_layer, tr_idx, d_m1_yb, d_m1_yt,
                                            unit_mode=True))

        return warrs

    def get_laygo_mos_yloc_info(self, lch_unit, w, **kwargs):
        # type: (int, float, **Any) -> Dict[str, Any]
        # get transistor constants
        mos_constants = self.get_mos_tech_constants(lch_unit)
        od_spy = mos_constants['od_spy']
        po_spy = mos_constants['po_spy']
        m1_gd_spy = mos_constants['m1_gd_spy']
        po_od_exty = mos_constants['po_od_exty']

        g_via_info = mos_constants['laygo_g_via']
        d_via_info = mos_constants['laygo_d_via']

        g_drc_info = self.get_conn_drc_info(lch_unit, 'g', is_laygo=True)
        drc_info = self.get_conn_drc_info(lch_unit, 'd', is_laygo=True)

        # convert w to resolution units
        layout_unit = self.config['layout_unit']
        res = self.res
        w_unit = int(round(w / layout_unit / res))

        # get minimum metal lengths
        # m1_min_len = drc_info[1]['min_len']
        # g_m1_w = g_drc_info[1]['w']
        m1_spy = max((info['sp_le'] for info in drc_info.values()))

        # compute gate location, based on PO-PO spacing
        po_yb = po_spy // 2

        g_co_yb = po_yb + g_via_info['bot_enc_le'][0]
        g_co_yt = g_co_yb + g_via_info['dim'][0][1]

        g_m1_yt = g_co_yt + g_via_info['top_enc_le'][0]
        g_m1_yb = g_m1_yt - g_drc_info[1]['min_len']

        # g_mx_yt = g_co_yc + g_via_info['dim'][0][1] + g_via_info['top_enc_le'][0]
        # g_mx_yb = g_mx_yt - md_min_len

        # compute drain/source location
        # first, get OD location from od_gd_spy
        od_yb = g_m1_yt + m1_gd_spy
        od_yt = od_yb + w_unit
        od_yc = (od_yb + od_yt) // 2

        # get number of vias
        d_v0_h = d_via_info['dim'][0][1]
        d_v0_sp = d_via_info['sp'][0]
        d_v0_od_ency = d_via_info['bot_enc_le'][0]
        d_v0_m1_ency = d_via_info['top_enc_le'][0]
        d_v0_n = (w_unit - 2 * d_v0_od_ency + d_v0_sp) // (d_v0_h + d_v0_sp)
        d_v0_arrh = d_v0_n * (d_v0_h + d_v0_sp) - d_v0_sp

        # get metal length and bottom metal coordinate
        m1_h = max(drc_info[1]['min_len'], d_v0_arrh + 2 * d_v0_m1_ency)
        d_m1_yb = od_yc

        # check sp_gd_m1 spec, move everything up if necessary
        delta = m1_gd_spy - (d_m1_yb - g_m1_yt)
        if delta > 0:
            d_m1_yb += delta
            od_yt += delta
            od_yb += delta
            od_yc += delta

        # compute final locations
        d_m1_yt = d_m1_yb + m1_h

        # find PO and block top Y coordinate
        po_yt = od_yt + po_od_exty
        blk_yt = po_yt + max(po_spy, m1_spy) // 2
        arr_y = 0, blk_yt

        # compute extension information
        g_y_list = [(g_m1_yb, g_m1_yt)]
        d_y_list = [(od_yb, od_yt)]
        return dict(
            blk=arr_y,
            po=(po_yb, po_yt),
            od=(od_yb, od_yt),
            top_margins=dict(
                od=(blk_yt - od_yt, od_spy),
                po=(blk_yt - po_yt, po_spy),
                m1=(blk_yt - d_m1_yt, m1_spy),
            ),
            bot_margins=dict(
                od=(od_yb, od_spy),
                po=(po_yb, po_spy),
                m1=(g_m1_yb, m1_spy),
            ),
            fill_info={},
            g_y_list=g_y_list,
            d_y_list=d_y_list,
        )

    def get_laygo_sub_yloc_info(self, lch_unit, w, **kwargs):
        # type: (int, float, **Any) -> Dict[str, Any]
        dnw_mode = kwargs.get('dnw_mode', '')
        blk_pitch = kwargs.get('blk_pitch', 1)

        mos_pitch = self.get_mos_pitch(unit_mode=True)
        md_min_len = self.get_md_min_len(lch_unit)
        mos_constants = self.get_mos_tech_constants(lch_unit)
        od_spy = mos_constants['od_spy']
        imp_od_ency = mos_constants['imp_od_ency']
        po_spy = mos_constants['po_spy']

        d_via_info = mos_constants['laygo_d_via']

        nw_dnw_ovl = mos_constants['nw_dnw_ovl']
        nw_dnw_ext = mos_constants['nw_dnw_ext']
        sub_m1_enc_le = mos_constants['sub_m1_enc_le']

        layout_unit = self.config['layout_unit']
        res = self.res
        od_h = int(round(w / layout_unit / (2 * res))) * 2

        # step 0: figure out implant/OD enclosure
        if dnw_mode:
            imp_od_ency = max(imp_od_ency, (nw_dnw_ovl + nw_dnw_ext - od_h) // 2)

        # step 1: find OD coordinate
        od_yb = imp_od_ency
        od_yt = od_yb + od_h
        blk_yt = od_yt + imp_od_ency
        # fix substrate height quantization, then recenter OD location
        blk_pitch = lcm([blk_pitch, mos_pitch])
        blk_yt = -(-blk_yt // blk_pitch) * blk_pitch
        od_yb = (blk_yt - od_h) // 2
        od_yt = od_yb + od_h
        od_yc = (od_yb + od_yt) // 2

        # step 2: find metal height

        drc_info = self.get_conn_drc_info(lch_unit, 'd', is_laygo=True)

        mx_spy = max((info['sp_le'] for info in drc_info.values()))
        d_v0_h = d_via_info['dim'][0][1]
        d_v0_sp = d_via_info['sp'][0]
        d_v0_od_ency = d_via_info['bot_enc_le'][0]
        d_v0_n = (od_h - 2 * d_v0_od_ency + d_v0_sp) // (d_v0_h + d_v0_sp)
        d_v0_arrh = d_v0_n * (d_v0_h + d_v0_sp) - d_v0_sp
        
        # mx_h = max(md_min_len, d_v0_arrh + 2 * sub_m1_enc_le)
        mx_h = max(md_min_len, d_v0_arrh + 2 * sub_m1_enc_le, od_h)

        d_mx_yb = od_yc - mx_h // 2
        d_mx_yt = d_mx_yb + mx_h

        mx_y = (d_mx_yb, d_mx_yt)
        return dict(
            blk=(0, blk_yt),
            po=(od_yb, od_yb),
            od=(od_yb, od_yt),
            top_margins=dict(
                od=(blk_yt - od_yt, od_spy),
                po=(blk_yt, po_spy),
                # mx=(blk_yt - d_mx_yt, mx_spy),
                m1=(blk_yt - d_mx_yt, mx_spy),
            ),
            bot_margins=dict(
                od=(od_yb, od_spy),
                po=(blk_yt, po_spy),
                # mx=(d_mx_yb, mx_spy),
                m1=(d_mx_yb, mx_spy),
            ),
            fill_info={},
            g_conn_y=mx_y,
            d_conn_y=mx_y,
        )
