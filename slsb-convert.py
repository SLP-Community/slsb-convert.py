# Script Version: 1.0 (to be used with SLSB v2.0.0+)
from typing import ClassVar, Iterable
from datetime import datetime
from pprint import pprint
from pathlib import Path
import subprocess
import argparse
import pathlib
import shutil
import json
import time
import os
import re

class Arguments:

    #required
    slsb_path:str|None = None           # path to slsb.exe
    parent_dir:str|None = None          # path to dir containing slal packs/modules
    #recommended
    skyrim_path:str|None = None         # path to `basegame_replica` directory
    remove_anims:bool = False           # True cleans up HKXs copied for behavior gen
    no_build:bool = False               # True skips building behaviour HKX files
    #public_release
    slate_path:str|None = None          # path to slate action logs
    slsb_json_path:str|None = None      # path to latest slsb project, for updates
    #optional
    stricter_futa:bool = False          # True skips assigning futa for positions with strap_on
    author:str|None = None              # name of the pack/conversion author
    #auto_determined
    fnis_path:str|None = None           # path to fnis for modders
    tmp_log_dir:str|None = None         # path to generated XMLs
    temp_dir:str|None = None            # for editing slsb json

    @staticmethod
    def setup_arguments():
        parser = argparse.ArgumentParser(prog='SexLab Catalytic Converter', description='Converts SLAL animation packs to SLSB automagically.')
        parser.add_argument('slsb', help='Path to SexLab_Scene_Builder.exe (slsb.exe).')
        parser.add_argument('parent', help='Path to directory containing SLAL packs; should be structured as {<parent_dir>/<slal_pack>/SLAnims/json/}.') 
        parser.add_argument('-s', '--skyrim', help='Path to skyrim base game directory (basegame_replica).')
        parser.add_argument('-ra', '--remove_anims', help='Cleans up animation meshes copied for behavior generation; safe to remove.', action='store_true')
        parser.add_argument('-nb', '--no_build', action='store_true', help='Skip building behaviour HKX files; useful for dry-testing script changes.')
        parser.add_argument('-slt', '--slate', dest='slate', help='Path to the directory containing SLATE action log json(s).')
        parser.add_argument('-upd', '--update', dest='update', help='Path to the directory containing SLSB project jsons; use if updating a public conversion.')
        parser.add_argument('-sf', '--stricter_futa', dest='stricter_futa', help='Skip additional futa flags for positions with strap-on (avoid, unless perfect alignments matter).', action='store_true')
        parser.add_argument('-a', '--author', help='Name of the SLAL pack author (avoid, unless converting a single pack).')
        args = parser.parse_args()
        return args

    @staticmethod
    def process_arguments():
        args = Arguments.setup_arguments()
        Arguments.slsb_path = os.path.abspath(args.slsb)
        Arguments.parent_dir = os.path.abspath(args.parent)
        Arguments.skyrim_path = os.path.abspath(args.skyrim)
        Arguments.remove_anims = args.remove_anims
        Arguments.no_build = args.no_build
        Arguments.slate_path = os.path.abspath(args.slate)
        Arguments.slsb_json_path = os.path.abspath(args.update)
        Arguments.stricter_futa = args.stricter_futa
        Arguments.author = args.author if args.author else 'Unknown'
        Arguments.fnis_path = os.path.join(Arguments.skyrim_path, 'Data/tools/GenerateFNIS_for_Modders') if args.skyrim else None
        Arguments.tmp_log_dir = os.path.join(Arguments.fnis_path, 'temporary_logs') if Arguments.fnis_path else None
        Arguments.temp_dir = os.path.join(Arguments.skyrim_path, 'tmp_slsb_dir')

    @staticmethod
    def debug(*content):
        return print(*content)

#############################################################################################
class Keywords:

    DOMINANT:list[str] = ['rough', 'bound', 'dominant', 'domsub', 'femdom', 'femaledomination', 'maledom', 'lezdom', 'gaydom', 'bdsm']
    FORCED:list[str] = ['force', 'forced', 'rape', 'fbrape', 'defeated', 'conquering', 'humiliation', 'estrus']
    USES_ONLY_AGG_TAG:list[str] = ['leito', 'kom', 'flufyfox', 'gs', 'cobalt', 'mastermike', 'nya', 'rydin', 'nibbles', 'anubs']
    UNCONSCIOUS:list[str] = ['necro', 'dead', 'unconscious']#, 'sleep', 'drunk', 'faint']
    FUTA:list[str] = ['futa', 'futanari', 'futaxfemale']
    LEADIN:list[str] = ['kissing', 'hugging', 'holding', 'loving', 'foreplay', 'lying', 'kneeling', 'cuddle', 'sfw', 'romance']
    NOT_LEADIN:list[str] = ['vaginal', 'anal', 'oral', 'blowjob', 'cunnilingus', 'forced', 'sex', 'masturbation']
    FEM_CRE_BODY_ONLY:list[str] = ['Chicken', 'Goat', 'Cow', 'Seeker', 'Wispmother', 'Hagraven', 'Spriggan', 'Flame Atronach']
    HENTAIRIM_TAGS:list[str] = ['kissing', 'stimulation', 'handjob', 'footjob', 'boobjob', 'blowjob', 'cunnilingus', 'oral',
        'cowgirl', 'vaginal', 'anal', 'spitroast', 'doublepenetration', 'triplepenetration']
    FURNITURE:list[str] = ['alchemywb', 'bed', 'bench', 'cage', 'chair', 'coffin', 'counter', 'couch', 'desk', 'doublebed', 'doublebeds', 'drawer',
        'dwemerchair', 'enchantingwb', 'furn', 'furotub', 'gallows', 'haybale', 'javtable', 'lowtable', 'necrochair', 'pillory', 'pillorylow',
        'pole', 'rpost', 'shack', 'sofa', 'spike', 'table', 'throne', 'torturerack', 'tub', 'wall', 'wheel', 'woodenpony', 'workbench', 'xcross']
    ALLOWED_FURN:dict[str, list[str]] = {
        'beds': ['BedRoll', 'BedDouble', 'BedSingle'],
        'walls': ['Wall', 'Railing'],
        'crafting': ['CraftCookingPot', 'CraftAlchemy', 'CraftEnchanting', 'CraftSmithing', 'CraftAnvil', 'CraftWorkbench', 'CraftGrindstone'],
        'tables': ['Table', 'TableCounter'],
        'chairs': ['Chair', 'ChairCommon', 'ChairWood', 'ChairBar', 'ChairNoble', 'ChairMisc'],
        'benches': ['Bench', 'BenchNoble', 'BenchMisc'],
        'thrones': ['Throne', 'ThroneRiften', 'ThroneNordic'],
        'contraptions': ['XCross', 'Pillory']}
    TIMESTAMP = datetime.now().strftime('[%Y.%m.%d_%H.%M.%S]')
    # Regex Patterns
    ANIM_PREFIX_PATTERN = re.compile(r'^\s*anim_name_prefix\("([^"]*)"\)')
    DIR_NAME_PATTERN = re.compile(r'anim_dir\("([^"]*)"\)')
    ANIM_START_PATTERN = re.compile(r'^\s*Animation\(')
    ANIM_END_PATTERN = re.compile(r'^\s*\)')
    ID_VALUE_PATTERN = re.compile(r'id="([^"]*)"')
    NAME_VALUE_PATTERN = re.compile(r'name="([^"]*)"')
    ACTOR_PATTERN = re.compile(r'actor\s*(\d+)\s*=\s*([^()]+)\(([^)]*)\)')
    BIGGUY_PATTERN = re.compile(r'(base\s?scale)\s?(\d+\.\d+)')
    SCALING_PATTERN = re.compile(r'(set\s?scale)\s?(\d+(?:\.\d+)?)?')

#############################################################################################
class StoredData:

    #session-specific mutables
    slsb_jsons_data:ClassVar[dict] = {}
    slate_logs_data:ClassVar[list] = []
    cached_variables:ClassVar[dict] = {'action_logs_found': False} # also stores {'slal_json_filename': anim_dir_name}
    xml_with_spaces:ClassVar[list[str]|str] = []
    #pack-specific mutables
    slal_jsons_data:ClassVar[dict] = {}
    source_txts_data:ClassVar[dict] = {}
    slal_fnislists_data:ClassVar[dict] = {}
    unique_animlist_options:ClassVar[list[str]|str] = []
    anim_cleanup_dirs:ClassVar[set] = set()
    #actor-stage-specific mutable
    tmp_params:ClassVar[dict] = {'has_strap_on': '', 'has_schlong': '', 'has_add_cum': ''}
    pos_counts:ClassVar[dict[str, int|bool]] = {}

    @staticmethod
    def reset_stored_data():
        StoredData.slal_jsons_data.clear()
        StoredData.source_txts_data.clear()
        StoredData.slal_fnislists_data.clear()
        StoredData.unique_animlist_options.clear()
        StoredData.anim_cleanup_dirs.clear()

#############################################################################################
class TagUtils:

    @staticmethod
    def if_any_found(tags:list[str], _any:list[str]|str, *extra_any:Iterable) -> False:
        if isinstance(_any, str):
            _any = [_any]
        if _any and any(item in tags for item in _any) or any(item in extra_check for extra_check in extra_any for item in _any):
            return True
        return False
    @staticmethod
    def if_then_add(tags:list[str], scene_name:str, anim_dir_name:str, _any:list[str]|str, not_any:list[str]|str, add:str) -> None:
        if add not in tags and TagUtils.if_any_found(tags, _any, scene_name, anim_dir_name) and not TagUtils.if_any_found(tags, not_any):
            tags.append(add)
    @staticmethod
    def if_then_add_simple(tags:list[str], _any:list[str]|str, add:str) -> None:
        if add not in tags and TagUtils.if_any_found(tags, _any):
            tags.append(add)
    @staticmethod
    def if_in_then_add(tags:list[str], _list:list[str], _any:list[str]|str, add:str) -> None:
        if add not in tags and TagUtils.if_any_found(_list, _any):
            tags.append(add)
    @staticmethod
    def if_then_remove(tags:list[str], all_in_tags:list[str], any_not_in_tags:list[str], remove:str) -> None:
        if remove in tags and all(item in tags for item in all_in_tags) and not TagUtils.if_any_found(tags, any_not_in_tags):
            tags.remove(remove)
    @staticmethod
    def if_then_replace(tags:list[str], remove:str, add:str) -> None:
        if remove in tags:
            tags.remove(remove)
            if add not in tags:
                tags.append(add)
    @staticmethod
    def bulk_add(tags:list[str], add:list[str]|str) -> None:
        if isinstance(add, str):
            add = [add]
        for item in add:
            if item and item not in tags:
                tags.append(item)
    @staticmethod
    def bulk_remove(tags:list[str], remove:list[str]|str) -> None:
        if isinstance(remove, str):
            remove = [remove]
        for item in remove:
            if item in tags:
                tags.remove(item)

#############################################################################################
class TagsRepairer:

    @staticmethod
    def update_stage_tags(name:str, tags:list[str], anim_dir_name:str) -> None:
        n = name.lower()
        d = anim_dir_name.lower()
        # tags corrections
        TagUtils.if_then_add(tags,'','', ['laying'], ['eggs', 'egg'], 'lying')
        TagUtils.if_then_remove(tags, ['laying', 'lying'], ['eggs', 'egg'], 'laying')
        TagUtils.if_then_replace(tags, 'invfurn', 'invisfurn')
        TagUtils.if_then_replace(tags, 'invisible obj', 'invisfurn')
        TagUtils.if_then_replace(tags, 'cunnilingius', 'cunnilingus')
        TagUtils.if_then_replace(tags, 'agressive', 'aggressive')
        TagUtils.if_then_replace(tags, 'femodm', 'femdom')
        # furniutre tags
        TagUtils.if_then_add(tags,n,d, ['inv'], '', 'invisfurn')
        TagUtils.if_then_add(tags,n,d, Keywords.FURNITURE, '', 'furniture')
        TagUtils.if_then_remove(tags, ['invisfurn', 'furniture'], '', 'furniture')
        # unofficial standardization
        TagUtils.if_then_add(tags,n,d, ['femdom', 'amazon', 'cowgirl', 'femaledomination', 'female domination', 'leito xcross standing'], '', 'femdom')
        TagUtils.if_then_add(tags,n,d, ['basescale', 'base scale', 'setscale', 'set scale', 'bigguy'], '', 'scaling')
        TagUtils.if_then_add(tags,n,d, Keywords.FUTA, '', 'futa')
        TagUtils.bulk_remove(tags, ['vampire', 'vampirelord']) # will be added later after special checks
        # official standard tags
        TagUtils.if_then_add(tags,n,d, ['mage', 'staff', 'alteration', 'rune', 'magicdildo', 'magick'], '', 'magic')
        TagUtils.if_then_add(tags,n,d, ['dp', 'doublepen'], '', 'doublepenetration')
        TagUtils.if_then_add(tags,n,d, ['tp', 'triplepen'], '', 'triplepenetration')
        TagUtils.if_then_add(tags,n,d, ['guro', 'execution'], '', 'gore')
        TagUtils.if_then_add(tags,n,d, ['choke', 'choking'], '', 'asphyxiation')
        TagUtils.if_then_add(tags,n,d, ['titfuck', 'tittyfuck'], '', 'boobjob')
        TagUtils.if_then_add(tags,n,d, ['trib', 'tribbing'], '', 'tribadism')
        TagUtils.if_then_add(tags,n,d, ['doggystyle', 'doggy'], '', 'doggy')
        TagUtils.if_then_add(tags,n,d, ['facesit'], '', 'facesitting')
        TagUtils.if_then_add(tags,n,d, ['lotus'], '', 'lotusposition')
        TagUtils.if_then_add(tags,n,d, ['spank'], '', 'spanking')
        TagUtils.if_then_add(tags,n,d, ['rimjob'], '', 'rimming')
        TagUtils.if_then_add(tags,n,d, ['kiss'], '', 'kissing')
        TagUtils.if_then_add(tags,n,d, ['hold'], '', 'holding')
        TagUtils.if_then_add(tags,n,d, ['69'], '', 'sixtynine')
        if '' in tags:
            tags.remove('')

    @staticmethod
    def fix_submissive_tags(tags:list[str], scene_name:str, anim_dir_name:str) -> None:
        sub_tags:dict[str,bool] = {
            'unconscious': False,   # necro stuff
            'gore': False,          # something gets chopped off
            'amputee': False,       # missing one/more limbs
            'ryona': False,         # dilebrately hurting sub
            'humiliation': False,   # includes punishments too
            'forced': False,        # rape and general non-consensual
            'asphyxiation': False,  # involving choking sub
            'spanking': False,      # you guessed it
            'dominant': False       # consensual bdsm
        }
        s = scene_name.lower()
        d = anim_dir_name.lower()
        # disibuting submissive flags for scenes (not flags for actors)
        if TagUtils.if_any_found(tags, Keywords.UNCONSCIOUS, s,d):
            sub_tags['unconscious'] = True
        if TagUtils.if_any_found(tags, ['guro', 'gore'], s,d): 
            sub_tags['gore'] = True
        if TagUtils.if_any_found(tags, ['amputee'], s,d): 
            sub_tags['amputee'] = True
        if TagUtils.if_any_found(tags, ['nya', 'molag', 'psycheslavepunishment'], s,d): 
            sub_tags['ryona'] = True
        if TagUtils.if_any_found(tags, ['humiliation', 'punishment'], s,d): 
            sub_tags['humiliation'] = True
        if TagUtils.if_any_found(tags, ['asphyxiation'], s,d): 
            sub_tags['asphyxiation'] = True
        if TagUtils.if_any_found(tags, ['spanking'], s,d): 
            sub_tags['spanking'] = True
        if TagUtils.if_any_found(tags, Keywords.DOMINANT, s,d):
            sub_tags['dominant'] = True
        # extensive treatment of forced scenes
        if TagUtils.if_any_found(tags, Keywords.FORCED, s,d):
            sub_tags['forced'] = True
        if 'aggressive' in tags:
            if TagUtils.if_any_found(tags, Keywords.USES_ONLY_AGG_TAG, s,d):
                sub_tags['forced'] = True
        # adjust stage tags based on sub_flags
        subtags_found:list[str] = []
        for sub_tag, flag_value in sub_tags.items():
            if flag_value:
                subtags_found.append(sub_tag)
                if sub_tag not in tags:
                    tags.append(sub_tag)
            elif not flag_value and sub_tag in tags:
                tags.remove(sub_tag)
        return subtags_found

    @staticmethod
    def insert_legacy_stage_counts(tags:list[str], stages_count:int, stage_num:int):
        legacy_stage_count_tag:str = 'stg_cnt_' + str(stages_count)
        legacy_stage_num_tag:str = 'stg_num_' + str(stage_num)
        TagUtils.bulk_add(tags, legacy_stage_num_tag)
        if stage_num == stages_count: # that is, is_end_stage:bool==True
            TagUtils.bulk_add(tags, legacy_stage_count_tag)

    @staticmethod
    def fix_leadin_tag(tags):
        TagUtils.if_then_remove(tags, ['leadin'], ['asltagged'], 'leadin')
        if any(kwd in tags for kwd in Keywords.LEADIN) and all(kwd not in tags for kwd in Keywords.NOT_LEADIN):
            TagUtils.bulk_add(tags, 'leadin')

    @staticmethod
    def fix_vampire_tags(name, tags, event_name, has_cre_vamplord):
        if has_cre_vamplord:
            TagUtils.bulk_add(tags, 'vampirelord')
        elif 'vamp' in event_name or 'vamp' in name.lower():
            TagUtils.bulk_add(tags, 'vampire')

    @staticmethod
    def fix_toys_tag(tags, anim_obj_found):
        if not anim_obj_found:
            TagUtils.bulk_remove(tags, 'toys')
        else:
            TagUtils.bulk_add(tags, 'toys')

#############################################################################################
class SLATE:

    @staticmethod
    def insert_slate_tags(tags:list[str]|str, name:str) -> None:
        if StoredData.cached_variables["action_logs_found"]:
            TagToAdd = ''
            TagToRemove = ''
            for entry in StoredData.slate_logs_data:
                if name.lower() == entry['anim'].lower():
                    if entry['action'].lower() == 'addtag':
                        TagToAdd = entry['tag'].lower()
                        if TagToAdd not in tags:
                            tags.append(TagToAdd)
                    elif entry['action'].lower() == 'removetag':
                        TagToRemove = entry['tag'].lower()
                        if TagToRemove in tags:
                            tags.remove(TagToRemove)

    @staticmethod
    def check_hentairim_tags(tags:list[str], stage_num:int, pos_ind:str) -> None:
        rimtags = {
            'ldi': '{stage}{pos}ldi',  # lead_in
            'kis': '{stage}{pos}kis',  # kissing
            'eno': '{stage}{pos}eno',  # end_penis_outside
            'eni': '{stage}{pos}eni',  # end_penis_inside
            # Stimulation Labels (actor getting cunnilingus/licking/fingering/etc)
            'sst': '{stage}{pos}sst',  # soft/slow
            'fst': '{stage}{pos}fst',  # intense/fast
            'bst': '{stage}{pos}bst',  # huge/fisting/big_non-pp_insertions
            # Oral Labels (what actor's mouth is doing)
            'cun': '{stage}{pos}cun',  # cunnilingus
            'sbj': '{stage}{pos}sbj',  # slow_giving_blowjob
            'fbj': '{stage}{pos}fbj',  # fast_giving_blowjob  
            # Penetration Labels (actor getting penile penetration)
            'svp': '{stage}{pos}svp',  # slow_vaginal
            'fvp': '{stage}{pos}fvp',  # fast_vaginal
            'sap': '{stage}{pos}sap',  # slow_anal
            'fap': '{stage}{pos}fap',  # fast_anal
            'scg': '{stage}{pos}scg',  # slow_vaginal_cowgirl
            'fcg': '{stage}{pos}fcg',  # fast_vaginal_cowgirl
            'sac': '{stage}{pos}sac',  # slow_anal_cowgirl
            'fac': '{stage}{pos}fac',  # fast_anal_cowgirl
            'sdp': '{stage}{pos}sdp',  # slow_double_pen
            'fdp': '{stage}{pos}fdp',  # fast_double_pen
            # Penis Action Labels (what actor's penis is doing)
            'sdv': '{stage}{pos}sdv',  # slow_giving_vaginal
            'fdv': '{stage}{pos}fdv',  # fast_giving_vaginal
            'sda': '{stage}{pos}sda',  # slow_giving_anal
            'fda': '{stage}{pos}fda',  # fast_giving_anal
            'shj': '{stage}{pos}shj',  # slow_getting_handjob
            'fhj': '{stage}{pos}fhj',  # fast_getting_handjob
            'stf': '{stage}{pos}stf',  # slow_getting_titfuck
            'ftf': '{stage}{pos}ftf',  # fast_getting_titfuck
            'smf': '{stage}{pos}smf',  # slow_getting_blowjob
            'fmf': '{stage}{pos}fmf',  # fast_getting_blowjob
            'sfj': '{stage}{pos}sfj',  # slow_getting_footjob
            'ffj': '{stage}{pos}ffj'   # fast_getting_footjob    
        }
        tags_set = set(tags)
        rimtags_found:list[str] = []
        non_stage_tags = set()
        for entry, dynamic_tag in rimtags.items():
            static_tag = dynamic_tag.format(stage=stage_num, pos=pos_ind)
            if static_tag in tags_set:
                rimtags_found.append(entry)
            # ensure stage-specifiicity for rim-tags
            for tag in tags:
                if tag.endswith(pos_ind+entry):
                    prefix = tag[:-len(pos_ind+entry)]
                    if prefix.isdigit() and int(prefix) != stage_num:
                        non_stage_tags.add(tag)
        if non_stage_tags:
            tags[:] = [tag for tag in tags if tag not in non_stage_tags]
        return rimtags_found

    @staticmethod
    def implement_hentairim_tags(tags:list[str], rimtags:list[str]) -> None:
        TagUtils.bulk_add(tags, ['rimtagged'])
        # removes all stage tags that would be added by HentaiRim
        if 'rimtagged' in tags and 'rim_ind' not in tags:
            TagUtils.bulk_remove(tags, [Keywords.HENTAIRIM_TAGS, 'leadin'])
            TagUtils.bulk_add(tags, ['rim_ind'])
        # each stage tagged differently based on HentaiRim interactions
        TagUtils.if_in_then_add(tags, rimtags, ['sst', 'fst', 'bst'], 'stimulation')
        TagUtils.if_in_then_add(tags, rimtags, ['kis'], 'kissing')
        TagUtils.if_in_then_add(tags, rimtags, ['shj', 'fhj'], 'handjob')
        TagUtils.if_in_then_add(tags, rimtags, ['sfj', 'ffj'], 'footjob')
        TagUtils.if_in_then_add(tags, rimtags, ['stf', 'ftf'], 'boobjob')
        TagUtils.if_in_then_add(tags, rimtags, ['sbj', 'fbj', 'smf', 'fmf'], 'blowjob')
        TagUtils.if_in_then_add(tags, rimtags, ['cun'], 'cunnilingus')
        TagUtils.if_in_then_add(tags, rimtags, ['sbj', 'fbj', 'smf', 'fmf', 'cun'], 'oral')
        TagUtils.if_in_then_add(tags, rimtags, ['scg', 'fcg', 'sac', 'fac'], 'cowgirl')
        TagUtils.if_in_then_add(tags, rimtags, ['svp', 'fvp', 'sdv', 'fdv', 'scg', 'fcg', 'sdp', 'fdp'], 'vaginal')
        TagUtils.if_in_then_add(tags, rimtags, ['sap', 'fap', 'sda', 'fda', 'sac', 'fac', 'sdp', 'fdp'], 'anal')
        if 'blowjob' in tags:
            TagUtils.if_then_add(tags,'','', 'vaginal', 'anal', 'spitroast')
            TagUtils.if_then_add(tags,'','', 'anal', 'vaginal', 'spitroast')
            TagUtils.if_then_add(tags,'','', ['vaginal', 'anal'], '', 'triplepenetration')
        if 'sdp' in rimtags or 'fdp' in rimtags:
            TagUtils.bulk_add(tags, 'doublepenetration')
        TagUtils.if_in_then_add(tags, rimtags, ['fst','bst','fvp','fap','fcg','fac','fdp','fdv','fda','fhj','ftf','fmf','ffj','fbj'], 'rimfast')
        TagUtils.if_in_then_add(tags, rimtags, ['sst','svp','sap','scg','sac','sdp','sdv','sda','shj','stf','smf','sfj','kis','cun','sbj'], 'rimslow')
        if not TagUtils.if_any_found(tags, Keywords.HENTAIRIM_TAGS):
            TagUtils.bulk_add(tags, 'leadin')

    @staticmethod
    def check_asl_tags(tags:list[str], stage_num:int) -> None:
        #if f'{stage_num}en' in tags:
        #    stage_num = stage_num - 1
        asltags = {
            'en': '{stage}en',  # end_stage
            'li': '{stage}li',  # lead_in
            'sb': '{stage}sb',  # slow_oral
            'fb': '{stage}fb',  # fast_oral
            'sv': '{stage}sv',  # slow_vaginal
            'fv': '{stage}fv',  # fast_vaginal
            'sa': '{stage}sa',  # slow_anal
            'fa': '{stage}fa',  # fast_anal
            'sr': '{stage}sr',  # spit_roast
            'dp': '{stage}dp',  # double_pen
            'tp': '{stage}tp',  # triple_pen
            'ba': '{stage}ba',  # ???
            'bv': '{stage}bv'   # ???
        }
        tags_set = set(tags)
        asltags_found:list[str] = []
        non_stage_tags = set()
        for entry, dynamic_tag in asltags.items():
            static_tag = dynamic_tag.format(stage=stage_num)
            if static_tag in tags_set:
                asltags_found.append(entry)
            # ensure stage-specifiicity for asl-tags
            for tag in tags:
                if tag.endswith(entry):
                    prefix = tag[:-len(entry)]
                    if prefix.isdigit() and int(prefix) != stage_num:
                        non_stage_tags.add(tag)
        if non_stage_tags:
            tags[:] = [tag for tag in tags if tag not in non_stage_tags]
        return asltags_found

    @staticmethod
    def implement_asl_tags(tags:list[str], asltags:list[str]) -> None:
        TagUtils.bulk_add(tags, ['asltagged'])
        if 'rimtagged' in tags:
            TagUtils.bulk_remove(tags, 'rim_ind')
            return
        # stores info on vaginal/anal tag presence (for spitroast)
        TagUtils.if_then_add(tags,'','', 'anal', 'vaginal', 'sranaltmp')
        TagUtils.if_then_add(tags,'','', 'vaginal', 'anal', 'srvagtmp')
        # removes all scene tags that would be added by ASL
        TagUtils.bulk_remove(tags, ['leadin', 'oral', 'vaginal', 'anal', 'spitroast', 'doublepenetration', 'triplepenetration'])
        # each stage tagged differently based on ASL interactions
        TagUtils.if_in_then_add(tags, asltags, ['li'], 'leadin')
        TagUtils.if_in_then_add(tags, asltags, ['sb', 'fb'], 'oral')
        TagUtils.if_in_then_add(tags, asltags, ['sv', 'fv'], 'vaginal')
        TagUtils.if_in_then_add(tags, asltags, ['sa', 'fa'], 'anal')
        if 'sr' in asltags:
            TagUtils.bulk_add(tags, ['spitroast', 'oral'])
            TagUtils.if_then_add_simple(tags, ['sranaltmp'], 'anal')
            TagUtils.if_then_add_simple(tags, ['srvagtmp'], 'vaginal')
        if 'dp' in asltags:
            TagUtils.bulk_add(tags, ['doublepenetration', 'vaginal', 'anal'])
        if 'tp' in asltags:
            TagUtils.bulk_add(tags, ['triplepenetration', 'oral', 'vaginal', 'anal'])
        TagUtils.if_in_then_add(tags, asltags, ['sb','sv','sa'], 'rimslow')
        TagUtils.if_in_then_add(tags, asltags, ['fb','fv','fa'], 'rimfast')
        TagUtils.bulk_remove(tags, ['sranaltmp', 'srvagtmp'])

    @staticmethod
    def correct_aslsfx_tags(tags:list[str], stage_num:int) -> None:
        aslsfx_tags = {
            'na': '{stage}na',  # no_sound
            'ks': '{stage}ks',  # kissing
            'ss': '{stage}ss',  # slow_slushing
            'ms': '{stage}ms',  # medium_slushing
            'fs': '{stage}fs',  # fast_slushing
            'rs': '{stage}rs',  # rapid_slushing
            'sc': '{stage}sc',  # slow_clapping (1/0.60s)
            'mc': '{stage}mc',  # medium_clapping (1/0.45s)
            'fc': '{stage}fc'   # fast_clapping (1/0.30s)
        }
        non_stage_tags = set()
        for entry, e in aslsfx_tags.items():
            for tag in tags:
                if tag.endswith(entry):
                    prefix = tag[:-len(entry)]
                    if prefix.isdigit() and int(prefix) != stage_num:
                        non_stage_tags.add(tag)
        if non_stage_tags:
            tags[:] = [tag for tag in tags if tag not in non_stage_tags]

    @staticmethod
    def implement_slate_tags(tags:list[str], stage_num:int, stage_positions:list[dict]) -> None:
        if StoredData.cached_variables["action_logs_found"]:
            rimtags:list[str] = []
            for i, tmp_stage_pos in enumerate(stage_positions):
                pos_ind:str = ''
                if i == 0:
                    pos_ind = 'a'
                elif i == 1:
                    pos_ind = 'b'
                elif i == 2:
                    pos_ind = 'c'
                elif i == 3:
                    pos_ind = 'd'
                elif i == 4:
                    pos_ind = 'e'
                rimtags_found:list[str] = SLATE.check_hentairim_tags(tags, stage_num, pos_ind)
                TagUtils.bulk_add(tmp_stage_pos['tags'], rimtags_found)     # rim_pos_tags (position specific tags)
                TagUtils.bulk_add(rimtags, rimtags_found)                   # appends unique rimtags_found to rimtags
            if rimtags:
                SLATE.implement_hentairim_tags(tags, rimtags)
            asltags:list[str] = SLATE.check_asl_tags(tags, stage_num)
            if asltags:
               SLATE.implement_asl_tags(tags, asltags)
            SLATE.correct_aslsfx_tags(tags, stage_num)

#############################################################################################
class Parsers:

    @staticmethod
    def parse_slal_json(file):
        json_array = json.load(file)
        for json_object in json_array:
            for scene_data in json_array["animations"]:
                scene_info = {
                    "scene_name": scene_data["name"],
                    "scene_id": scene_data["id"],
                    "scene_tags": scene_data["tags"].split(","),
                    "scene_sound": scene_data["sound"],
                    "actors": {},
                    "stage_params": {}
                }
                for key, actor_data in enumerate(scene_data["actors"], 1):
                    actor_key = f"a{key}"
                    actor_info = {
                        "actor_key": actor_key,
                        "gender": actor_data["type"],
                        "add_cum": actor_data.get("add_cum", 0),
                        f"{actor_key}_stage_params": {}
                    }
                    for idx, actor_stage_data in enumerate(actor_data["stages"], 1):
                        actor_stage_params_key = f"Stage {idx}"
                        actor_stage_params_info = {
                            "actor_stage_params_key": actor_stage_params_key,
                            "stage_id": actor_stage_data["id"],
                            "open_mouth": actor_stage_data.get("open_mouth", "False"),
                            "strap_on": actor_stage_data.get("strap_on", "False"),
                            "silent": actor_stage_data.get("silent", "False"),
                            "sos": actor_stage_data.get("sos", 0),
                            "up": actor_stage_data.get("up", 0),
                            "side": actor_stage_data.get("side", 0),
                            "rotate": actor_stage_data.get("rotate", 0),
                            "forward": actor_stage_data.get("forward", 0)
                        }
                        actor_info[f"{actor_key}_stage_params"][actor_stage_params_key] = actor_stage_params_info
                    
                    scene_info["actors"][actor_key] = actor_info
                
                for scene_stage_data in scene_data.get("stages", []):
                    stage_params_key = f"Stage {scene_stage_data.get('number', 'None')}"
                    
                    scene_stage_params_info = {
                        "stage_params_key": stage_params_key,
                        "sound": scene_stage_data.get("sound", "None"),
                        "timer": scene_stage_data.get("timer", 0)
                    }
                    scene_info["stage_params"][stage_params_key] = scene_stage_params_info

                StoredData.slal_jsons_data[scene_info["scene_name"]] = scene_info

    @staticmethod
    def parse_slsb_jsons(file):
        parsed_json = json.load(file)
        pack_info = {
            'pack_name': parsed_json['pack_name'],
            'pack_hash': parsed_json['prefix_hash'],
            'pack_author': parsed_json['pack_author'],
            'scenes': {}
        }
        for scene in parsed_json['scenes']:
            scene_data = parsed_json['scenes'][scene]
            scene_info = {
                'scene_hash': scene_data['id'],
                'scene_name': scene_data['name'],
                'scene_stages': {},
                'scene_root': scene_data['root'],
                'scene_graph': scene_data["graph"]
            }
            for i in range(len(scene_data['stages'])):
                stage_data = scene_data['stages'][i]
                stage_info = {
                    'stage_hash': stage_data['id'],
                    'stage_name': stage_data['name'],
                    'navigation_text': stage_data['extra']['nav_text']
                }
                scene_info['scene_stages'][i] = stage_info

            pack_info['scenes'][scene] = scene_info

        StoredData.slsb_jsons_data[pack_info['pack_name']] = pack_info

    @staticmethod
    def parse_source_txt(file):
        inside_animation:bool = False
        anim_name_prefix:str = ''
        anim_full_name:str = ''

        for line in file:
            line = line.strip()
            if line:

                anim_prefix_match = Keywords.ANIM_PREFIX_PATTERN.search(line)
                anim_start_indicator = Keywords.ANIM_START_PATTERN.match(line)
                anim_end_indicator = Keywords.ANIM_END_PATTERN.match(line)
                id_value = Keywords.ID_VALUE_PATTERN.search(line)
                name_value = Keywords.NAME_VALUE_PATTERN.search(line)
                actor_match = Keywords.ACTOR_PATTERN.search(line)

                if anim_prefix_match:
                    anim_name_prefix = anim_prefix_match.group(1)

                elif anim_start_indicator:
                    source_txt_scenes = {'anim_name_prefix': anim_name_prefix, 'id': '', 'bare_name': '', 'actors': {}}
                    inside_animation = True

                if inside_animation:
                    if id_value:
                        source_txt_scenes['id'] = id_value.group(1)
                    elif name_value:
                        source_txt_scenes['bare_name'] = name_value.group(1)
                        anim_full_name = anim_name_prefix + source_txt_scenes['bare_name']
                    elif actor_match:
                        actor_number = actor_match.group(1)
                        actor_gender = actor_match.group(2)
                        source_txt_scenes['actors'][actor_number] = {'actor_gender': actor_gender}

                    elif anim_end_indicator:
                        StoredData.source_txts_data[anim_full_name] = source_txt_scenes
                        inside_animation = False

    @staticmethod
    def parse_slal_fnislists(parent_dir,_dir, file):
        path = os.path.join(parent_dir, file)
        with open(path, 'r') as topo_file:
            last_seq = None
            for line in topo_file:
                line = line.strip()
                if len(line) > 0 and line[0] != "'":
                    splits = line.split()
                    if (len(splits)) == 0 or splits[0].lower() in ('version', 'ï»¿version'):
                        continue

                    anim_file_name:str|None = None
                    anim_event_name:str|None = None
                    options:list[str] = []
                    anim_objects:list[str] = []

                    for i in range(len(splits)):
                        split = splits[i]
                        if anim_event_name is not None and split not in anim_objects:
                            anim_objects.append(split)
                        if '.hkx' in split.lower():
                            anim_file_name = splits[i]
                            anim_event_name = splits[i - 1]
                        if split.startswith("-"):
                            options_list = split[1:].split(",")
                            for item in options_list:
                                if item.lower() not in ('avbhumanoidfootikdisable', 'tn', 'o', 'a') and item not in options:
                                    options.append(item)

                    if options:
                        StoredData.unique_animlist_options.extend([anim_file_name, options])
                    
                    anim_event_name = anim_event_name.lower()
                    if '-a,' in line or '-a ' in line or '-o,a,' in line or '-o,a ' in line:
                        last_seq = anim_event_name
                    
                    anim_path = os.path.join(parent_dir, anim_file_name)
                    out_path = os.path.normpath(anim_path)
                    out_path = out_path.split(os.sep)

                    for i in range(len(out_path) - 1, -1, -1):
                        if (out_path[i].lower() == 'meshes'):
                            out_path = out_path[i:]
                            break
                
                    out_path = os.path.join('', *out_path)
                    
                    data = {
                        'anim_file_name': anim_file_name,
                        'options': options,
                        'anim_obj': anim_objects,
                        'path': anim_path,
                        'out_path': out_path,
                        'sequence': []
                    }

                    if last_seq is None:
                        StoredData.slal_fnislists_data[anim_event_name] = data
                    else:
                        try:
                            StoredData.slal_fnislists_data[last_seq]['sequence'].append(data)
                            # Don't know what this is supposed to do; the ['sequence'] is empty so always KeyError
                        except KeyError:
                            StoredData.slal_fnislists_data[last_seq] = data
                    last_seq = None

    @staticmethod 
    def parse_slate_actionlogs(file):
        info = json.load(file)
        string_list = info["stringList"]["slate.actionlog"]
        
        for item in string_list:
            action, anim, tag = item.split(',', 2)
            action = action.lower()
            anim = anim.strip()
            tag = tag.strip()
            
            StoredData.slate_logs_data.append({
                "action": action,
                "anim": anim,
                "tag": tag
            })

#############################################################################################
class Editors:

    @staticmethod
    def fix_slal_jsons(working_dir):
        anim_source_dir = working_dir + "\\SLAnims\\source"
        slal_jsons_dir = working_dir + "\\SLAnims\\json"
        anim_meshes_dir = working_dir + "\\meshes\\actors\\character\\animations"

        def prompt_for_existing_dir(dirs, anim_dir_path, json_base_name):
            Arguments.debug(f"\nERROR: Could not auto-determine AnimDirName for: {json_base_name}.json")
            if not dirs:
                raise ValueError(f"No valid directories found in {anim_dir_path}")
            Arguments.debug("Please select from these existing directories:")
            for i, d in enumerate(dirs, 1):
                Arguments.debug(f"{i}. {d}")
            while True:
                try:
                    choice = int(input("\nEnter number (1-{}): ".format(len(dirs))))
                    if 1 <= choice <= len(dirs):
                        return dirs[choice-1]
                    Arguments.debug("Invalid number, try again")
                except ValueError:
                    Arguments.debug("Please enter a valid number")

        def find_animdirname(filename, slal_json_path):
            if os.path.isfile(slal_json_path) and filename.lower().endswith(".json"):
                json_base_name = pathlib.Path(filename).stem
                if json_base_name not in StoredData.cached_variables:
                    StoredData.cached_variables[json_base_name] = {}
                matching_source_path = None
                if os.path.exists(anim_source_dir):
                    for source_file in os.listdir(anim_source_dir):
                        if source_file.lower().endswith(".txt") and pathlib.Path(source_file).stem.lower() == json_base_name.lower():
                            matching_source_path = os.path.join(anim_source_dir, source_file)
                            break
                    if matching_source_path is not None:
                        with open(matching_source_path, 'r') as txt_file:
                            for line in txt_file:
                                anim_dir_match = Keywords.DIR_NAME_PATTERN.search(line)
                                if anim_dir_match:
                                    StoredData.cached_variables[json_base_name]['anim_dir_name'] = anim_dir_match.group(1)
                                    break
                if (not os.path.exists(anim_source_dir) and os.path.exists(anim_meshes_dir)) \
                    or (os.path.exists(anim_source_dir) and matching_source_path is None):
                    dirs = [d for d in os.listdir(anim_meshes_dir) if os.path.isdir(os.path.join(anim_meshes_dir, d))]
                    if len(dirs) == 1:
                        StoredData.cached_variables[json_base_name]['anim_dir_name'] = dirs[0]
                    else:
                        potential_dir = os.path.join(anim_meshes_dir, json_base_name)
                        if os.path.isdir(potential_dir):
                            StoredData.cached_variables[json_base_name]['anim_dir_name'] = json_base_name
                        else:
                            selected_dir = prompt_for_existing_dir(dirs, anim_meshes_dir, json_base_name)
                            StoredData.cached_variables[json_base_name]['anim_dir_name'] = selected_dir

                return StoredData.cached_variables[json_base_name]['anim_dir_name']

        def fix_typegender(json_data):
            changes_made:bool = False
            if "animations" in json_data:
                for scene_data in json_data["animations"]:
                    for key, actor_data in enumerate(scene_data["actors"], 1):
                        if actor_data["type"].lower() == "type":
                            anim_name_with_type = scene_data["name"]
                            if anim_name_with_type in StoredData.source_txts_data:
                                required_scene_data = StoredData.source_txts_data[anim_name_with_type]
                                if str(key) in required_scene_data['actors']:
                                    required_actor_data = required_scene_data['actors'][str(key)]
                                    actor_data["type"] = required_actor_data['actor_gender']
                                    changes_made = True
            return changes_made

        for filename in os.listdir(slal_jsons_dir):
            slal_json_path = os.path.join(slal_jsons_dir, filename)
            anim_dir_name:str = find_animdirname(filename, slal_json_path)
            changes_made:bool = False
            with open(slal_json_path, 'r+') as json_file:
                json_data = json.load(json_file)
                # Fix directory name
                if anim_dir_name and "name" in json_data and json_data["name"].lower() != anim_dir_name.lower():
                    json_data["name"] = anim_dir_name
                    changes_made = True
                # Fix type-type gender
                if fix_typegender(json_data):
                    changes_made = True
                # Edit the SLAL json
                if changes_made:
                    Arguments.debug("---------> FIXING SLAL JSONs")
                    json_file.seek(0)
                    json.dump(json_data, json_file, indent=2)
                    json_file.truncate()

    @staticmethod
    def edit_output_fnis(file_path, _dir, filename):
        full_path = os.path.join(file_path, filename)
        modified_lines = []

        with open(full_path, 'r') as file:
            for line in file:
                splits = line.split()
                for i in range(len(splits)):
                    
                    if splits[i] in StoredData.unique_animlist_options:
                        idx = StoredData.unique_animlist_options.index(splits[i])
                        options = ",".join(StoredData.unique_animlist_options[idx + 1])
                        if splits[i-2] == "b":
                            splits[i-2] = f"b -{options}"
                        if splits[i-2] == "-o":
                            splits[i-2] = f"-o,{options}"
                        if splits[i-2] == "-a,tn":
                            splits[i-2] = f"-a,tn,{options}"
                        if splits[i-2] == "-o,a,tn":
                            splits[i-2] = f"-o,a,tn,{options}"
                        line = " ".join(splits) + "\n"

                modified_lines.append(line)
        with open(full_path, 'w') as file:
            file.writelines(modified_lines)

#############################################################################################
class ActorUtils:

    @staticmethod
    def process_pos_flag_futa_1(tags:list[str], scene_pos:dict[str,any], pos_length:int, pos_num:int, event_name:str):
        # initial preparations
        if 'futa' not in tags:
            return
        if 'kom_futaduo' in event_name:
            scene_pos['sex']['female'] = False
            scene_pos['sex']['male'] = True
        if 'futafurniture01(bed)' in event_name:
            if pos_num == 0:
                scene_pos['sex']['female'] = False
                scene_pos['sex']['futa'] = True
            if pos_num == 1:
                scene_pos['sex']['male'] = False
                scene_pos['sex']['female'] = True
        if 'gs' in tags and 'mf' in tags and pos_length == 2:
            if not scene_pos['sex']['male'] and pos_num == 1:
                scene_pos['sex']['female'] = False
                scene_pos['sex']['futa'] = True

    @staticmethod
    def process_pos_flag_sub(tags:list[str], scene_pos:dict[str,any], pos_num:int, sub_tags:list[str], is_sub_scene:bool):
        # IMP: Deal with sub/dead flags before futa flags
        if is_sub_scene:
            straight:bool = StoredData.pos_counts['straight']
            lesbian:bool = StoredData.pos_counts['lesbian']
            gay:bool = StoredData.pos_counts['gay']
            male_count:int = StoredData.pos_counts['male']
            female_count:int = StoredData.pos_counts['female']
            
            if straight and female_count == 1 and 'femdom' not in tags and scene_pos['sex']['female']:
                scene_pos['submissive'] = True
            if straight and female_count == 2 and 'femdom' not in tags: #needs_testing
                if scene_pos['sex']['female']:
                    scene_pos['submissive'] = True
            if straight and ('femdom' in tags or 'ffffm' in tags) and scene_pos['sex']['male']:
                scene_pos['submissive'] = True
            if gay and ((male_count == 2 and pos_num == 0) or ('hcos' in tags and scene_pos['race'] in {'Rabbit', 'Skeever', 'Horse'})): # needs_testing
                scene_pos['submissive'] = True
            if lesbian and pos_num == 0: # needs_testing
                scene_pos['submissive'] = True

            if TagUtils.if_any_found(sub_tags, ['unconscious', 'gore', 'amputee']) and scene_pos['submissive']:
                scene_pos['submissive'] = False
                scene_pos['dead'] = True
            #if 'billyy' in tags and 'cf' in tags and scene_pos['submissive']:
            #   scene_pos['submissive'] = False

    @staticmethod
    def process_pos_flag_futa_2(tags:list[str], scene_pos:dict[str,any], pos_num:int, actor_key:str):
        if 'futa' not in tags:
            return
        if 'anubs' in tags and ('ff' in tags or 'fff' in tags):
            if actor_key[1:] in StoredData.tmp_params['has_schlong']:
                if pos_num == int(actor_key[1:]) - 1:
                    scene_pos['sex']['female'] = False
                    scene_pos['sex']['futa'] = True
        if 'flufyfox' in tags or 'milky' in tags:
            if actor_key[1:] in StoredData.tmp_params['has_strap_on']:
                if pos_num == int(actor_key[1:]) - 1:
                    scene_pos['sex']['female'] = False
                    scene_pos['sex']['futa'] = True

    @staticmethod
    def process_pos_flag_futa_3(tags:list[str], scene_pos:dict[str,any], pos_length:int, pos_num:int):
        if 'futa' not in tags:
            return
        if 'solo' in tags or 'futaall' in tags or ('anubs' in tags and 'mf' in tags) or ('ff' in tags and ('frotting' in tags or 'milking' in tags)):
            if scene_pos['sex']['female']:
                scene_pos['sex']['female'] = False
                scene_pos['sex']['futa'] = True
        elif 'billyy' in tags and '2futa' in tags and pos_length == 3:
            if pos_num == 0|1:
                scene_pos['sex']['female'] = False
                scene_pos['sex']['futa'] = True
        elif 'ff' in tags and scene_pos['sex']['male']:
            scene_pos['sex']['male'] = False
            scene_pos['sex']['futa'] = True

    @staticmethod
    def process_pos_flag_vampire(tags:list[str], scene_pos:dict[str,any], event_name:str):
        if 'vampire' not in tags:
            return
        if TagUtils.if_any_found(tags, ['vampirefemale','vampirelesbian', 'femdom', 'cowgirl', 'vampfeedf'], event_name) and scene_pos['sex']['female']:
            scene_pos['vampire'] = True
        elif scene_pos['sex']['male']:
            scene_pos['vampire'] = True

    @staticmethod
    def process_pos_scaling(name:str, tags:list[str], scene_pos:dict[str,any]):
        if not ('bigguy' in tags or 'scaling' in tags):
            return
        bigguy_value = Keywords.BIGGUY_PATTERN.search(name.lower())
        scaling_value = Keywords.SCALING_PATTERN.search(name.lower())
        if bigguy_value:
            if scene_pos['sex']['male']:
                scene_pos['scale'] = round(float(bigguy_value.group(2)), 2)
        if scaling_value:
            value = round(float(scaling_value.group(2)), 2)
            if 'gs orc' in name.lower() and scene_pos['sex']['male']:
                scene_pos['scale'] = value
            if 'gs giantess' in name.lower() and scene_pos['sex']['female']:
                scene_pos['scale'] = value
            if 'hcos small' in name.lower() and scene_pos['race'] == 'Dragon':
                scene_pos['scale'] = value

    @staticmethod
    def process_pos_leadin(tags:list[str], stage_pos:dict[str,any]):
        if 'leadin' in tags:
            stage_pos['strip_data']['default'] = False
            stage_pos['strip_data']['helmet'] = True
            stage_pos['strip_data']['gloves'] = True

    @staticmethod
    def process_pos_animobjects(stage_pos:dict[str,any], event_name:str, out_dir:str):
        if event_name and event_name in StoredData.slal_fnislists_data.keys():
            required_info = StoredData.slal_fnislists_data[event_name]
            stage_pos['event'][0] = os.path.splitext(required_info['anim_file_name'])[0]
            if Arguments.skyrim_path is not None:
                os.makedirs(os.path.dirname(os.path.join(out_dir, required_info['out_path'])), exist_ok=True)
                shutil.copyfile(required_info['path'], os.path.join(out_dir, required_info['out_path']))
            if 'anim_obj' in required_info and required_info['anim_obj'] is not None:
                stage_pos['anim_obj'] = ','.join(required_info['anim_obj'])

    @staticmethod
    def allow_flexible_futa(scene_pos:dict[str,any], pos_num:int, actor_key:str):
        if Arguments.stricter_futa:
            return
        if actor_key[1:] in StoredData.tmp_params['has_strap_on']:
            if pos_num == int(actor_key[1:]) - 1:
                if scene_pos['race'] == 'Human':
                    scene_pos['sex']['futa'] = True

    @staticmethod
    def relax_creature_gender(scene_pos:dict[str,any]):
        if scene_pos['race'] in Keywords.FEM_CRE_BODY_ONLY:
            scene_pos['sex']['female'] = True
            scene_pos['sex']['male'] = True
        if StoredData.pos_counts['human_male'] and StoredData.pos_counts['cre_female'] and \
            (StoredData.pos_counts['cre_male'] + StoredData.pos_counts['human_female'] == 0):
            if scene_pos['sex']['male']:
                scene_pos['sex']['futa'] = True

#############################################################################################
class ParamUtils:

    @staticmethod
    def process_actorstage_params(params_data, stage_pos:dict[str,any], stage_num:int, pos_num:int, actor_key:str, event_key:str):

        def process_pos_sos():
            if 'sos' in params_data and params_data['sos'] != 0:
                # for sos value integration
                #has_sos_value = event_key
                #if (event_key in has_sos_value) and (stage_num == int(event_key[4:])) and (pos_num == int(actor_key[1:]) - 1):
                #   stage_pos['schlong'] = params_data['sos']
                # for futa
                if StoredData.tmp_params['has_schlong'] and actor_key[1:] not in StoredData.tmp_params['has_schlong']:
                    StoredData.tmp_params['has_schlong'] += f",{actor_key[1:]}"
                else:
                    StoredData.tmp_params['has_schlong'] = actor_key[1:]
   
        def process_pos_strapon():
            if 'strap_on' in params_data and params_data['strap_on'] != "False":
                if StoredData.tmp_params['has_strap_on'] and actor_key[1:] not in StoredData.tmp_params['has_strap_on']:
                    StoredData.tmp_params['has_strap_on'] += f",{actor_key[1:]}"
                else:
                    StoredData.tmp_params['has_strap_on'] = actor_key[1:]

        def process_pos_offsets():
            if 'forward' in params_data and params_data['forward'] != 0:
                has_forward = event_key
                if event_key in has_forward and int(event_key[4:]) == stage_num:
                    if pos_num == int(actor_key[1:]) - 1:
                        stage_pos['offset']['y'] = params_data['forward']
            if 'side' in params_data and params_data['side'] != 0:
                has_side = event_key
                if event_key in has_side and int(event_key[4:]) == stage_num:
                    if pos_num == int(actor_key[1:]) - 1:
                        stage_pos['offset']['x'] = params_data['side']
            if 'up' in params_data and params_data['up'] != 0:
                has_up = event_key
                if event_key in has_up and int(event_key[4:]) == stage_num:
                    if pos_num == int(actor_key[1:]) - 1:
                        stage_pos['offset']['z'] = params_data['up']
            if 'rotate' in params_data and params_data['rotate'] != 0:
                has_rotate = event_key
                if event_key in has_rotate and int(event_key[4:]) == stage_num:
                    if pos_num == int(actor_key[1:]) - 1:
                        stage_pos['offset']['r'] = params_data['rotate']

        # - - - - - - - - - - - - -
        process_pos_sos()
        process_pos_strapon()
        process_pos_offsets()
        # - - - - - - - - - - - - -

    @staticmethod
    def process_actor_params(params_data, stage_pos:dict[str,any], stage_num:int, pos_num:int, actor_key:str):

        def process_pos_cum():
            if 'add_cum' in params_data and params_data['add_cum'] != 0:
                if StoredData.tmp_params['has_add_cum'] and actor_key[1:] not in StoredData.tmp_params['has_add_cum']:
                    StoredData.tmp_params['has_add_cum'] += f",{actor_key[1:]}"
                else:
                    StoredData.tmp_params['has_add_cum'] = actor_key[1:]

        def initiate_actor_stage_params():
            actor_stage_params_map = params_data[f'{actor_key}_stage_params']
            for key, value in actor_stage_params_map.items():
                actor_stage_params_key = key
                event_key = f"{actor_key}" + f"_s{actor_stage_params_key[6:]}"
                if actor_stage_params_key.startswith('Stage'):
                    source_actor_stage_params = actor_stage_params_map[actor_stage_params_key]
                    ParamUtils.process_actorstage_params(source_actor_stage_params, stage_pos, stage_num, pos_num, actor_key, event_key)

        # - - - - - - - - - - - - -
        process_pos_cum()
        initiate_actor_stage_params()
        # - - - - - - - - - - - - -

    @staticmethod
    def incorporate_slal_json_data(name:str, stage_num:int, tags:list[str], scene_pos:dict[str,any], stage_pos:dict[str,any], pos_num:int):
        if name in StoredData.slal_jsons_data:
            slal_json_data = StoredData.slal_jsons_data[name]
            actor_map = slal_json_data['actors']
            for i, actor_dict in enumerate(actor_map):
                for key, value in actor_map.items():
                    actor_key = key
                    if actor_key.startswith('a'):
                        source_actor_data = actor_map[actor_key]
                        ParamUtils.process_actor_params(source_actor_data, stage_pos, stage_num, pos_num, actor_key)
                        # Actor-Specific Fine Tuning
                        ActorUtils.process_pos_flag_futa_2(tags, scene_pos, pos_num, actor_key)
                        ActorUtils.allow_flexible_futa(scene_pos, pos_num, actor_key)

    @staticmethod
    def process_stage_params(name:str, stage:dict[str,any], stage_num:int):
        if name not in StoredData.slal_jsons_data:
            return
        slal_json_data = StoredData.slal_jsons_data[name]
        stage_params_map = slal_json_data['stage_params']
        for key, value in stage_params_map.items():
            stage_params_key = key
            if stage_params_key.startswith('Stage'):
                source_stage_params = stage_params_map[stage_params_key]

                if 'timer' in source_stage_params and source_stage_params['timer'] != 0:
                    if int(stage_params_key[6:]) == stage_num:
                        #fixed_length = round(float(source_stage_params['timer']), 2)
                        fixed_length = round(float(source_stage_params['timer']) * 1000) #timers in miliseconds
                        stage['extra']['fixed_len'] = fixed_length

#############################################################################################
class StageUtils:

    @staticmethod
    def update_pos_counts(scene_positions:list[dict]):
        def reset_pos_counts():
            for key in ['male', 'female', 'human_male', 'cre_male', 'human_female', 'cre_female', 'cre_count']:
                StoredData.pos_counts[key] = 0
            for key in ['straight', 'gay', 'lesbian']:
                StoredData.pos_counts[key] = False
        reset_pos_counts()
        for tmp_scene_pos in scene_positions:
            is_human = (tmp_scene_pos['race'] == 'Human')
            if tmp_scene_pos['sex']['male']:
                StoredData.pos_counts['male'] += 1
                StoredData.pos_counts['human_male' if is_human else 'cre_male'] += 1
            if tmp_scene_pos['sex']['female']:
                StoredData.pos_counts['female'] += 1
                StoredData.pos_counts['human_female' if is_human else 'cre_female'] += 1
        StoredData.pos_counts['cre_count'] = StoredData.pos_counts['cre_male'] + StoredData.pos_counts['cre_female']
        male_count = StoredData.pos_counts['male']
        female_count = StoredData.pos_counts['female']
        StoredData.pos_counts['straight'] = male_count > 0 and female_count > 0
        StoredData.pos_counts['gay'] = male_count > 0 and female_count == 0
        StoredData.pos_counts['lesbian'] = male_count == 0 and female_count > 0

    @staticmethod
    def process_stage_furniture(name:str, tags:list[str], furniture:dict, pos_length:int, anim_obj_found:bool):
        
        def incorporate_allowbed():
            if anim_obj_found or pos_length > 2:
                return
            if 'invisfurn' in tags or 'lying' not in tags or StoredData.pos_counts['cre_count'] > 0 :
                return
            furniture['allow_bed'] = True
            TagUtils.bulk_add(tags, 'allowbed')

        def incorporate_invisfurn():
            if 'invisfurn' not in tags:
                return
            if 'bed' in name.lower():
                furniture['furni_types'] = Keywords.ALLOWED_FURN['beds']
            if 'chair' in name.lower():
                furniture['furni_types'] = Keywords.ALLOWED_FURN['chairs'] + Keywords.ALLOWED_FURN['thrones']
            if 'wall' in name.lower():
                furniture['furni_types'] = Keywords.ALLOWED_FURN['walls']
            if 'table' in name.lower():
                furniture['furni_types'] = [Keywords.ALLOWED_FURN['tables'][0]]
            if 'counter' in name.lower():
                furniture['furni_types'] = [Keywords.ALLOWED_FURN['tables'][1]]

        # - - - - - - - - - - - - -
        incorporate_allowbed()
        incorporate_invisfurn()
        # - - - - - - - - - - - - -

#############################################################################################
class StageProcessor:

    @staticmethod
    def process_stage(scene_name, scene_tags, stage, stage_num, out_dir):
        stage_tags:list[str] = []
        stage['tags'] = stage_tags
        stage_positions:list[dict] = stage['positions']

        pos_length:int = len(stage_positions)
        for i in range(pos_length):
            stage_pos:dict[str,any] = stage_positions[i]
            pos_num:int = i
            event_name:str|None = None
            if stage_pos['event'] and len(stage_pos['event']) > 0:
                event_name = stage_pos['event'][0].lower()
            ActorUtils.process_pos_animobjects(stage_pos, event_name, out_dir)
            ParamUtils.incorporate_slal_json_data(scene_name, [], [], stage_pos, stage_num, pos_num, 'Stage')
            #ActorUtils.process_pos_leadin(scene_tags, stage_pos)
        
        ParamUtils.process_stage_params(scene_name, stage, stage_num)
        SLATE.implement_slate_tags(scene_tags, stage_tags, stage_num, stage_positions)

        stage['tags'] = stage_tags
        #-----------------

    @staticmethod
    def process_scene(scene, anim_dir_name, out_dir):
        scene_name:str = scene['name']
        stages:list[dict] = scene['stages']
        scene_positions:list[dict] = scene['positions']
        furniture:dict[str,any] = scene['furniture']

        first_event_name:str|None = None
        fist_event:str = stages[0]['positions'][0]['event']
        if fist_event and len(fist_event) > 0:
            first_event_name = fist_event[0].lower()

        scene_tags:list[str] = [slal_tag.lower().strip() for slal_tag in stages[0]['tags']]
        SLATE.insert_slate_tags(scene_tags, scene_name)
        TagsRepairer.update_scene_tags(scene_name, scene_tags, anim_dir_name)
        TagsRepairer.fix_leadin_tag(scene_tags)

        anim_obj_found:bool = False
        for i in range(len(stages)):
            stage = stages[i]
            stage_num = i + 1
            StageProcessor.process_stage(scene_name, scene_tags, stage, stage_num, out_dir)
            if not anim_obj_found:
                anim_obj_found = any(tmp_stage_pos['anim_obj'] != '' and 'cum' not in tmp_stage_pos['anim_obj'].lower() for tmp_stage_pos in stage['positions'])

        StageUtils.update_pos_counts(scene_positions)
        has_cre_vamplord:bool = any(tmp_scene_pos['race']=="Vampire Lord" for tmp_scene_pos in scene_positions)
        is_sub_scene:bool = False
        sub_tags:list[str] = TagsRepairer.fix_submissive_tags(scene_tags, scene_name, anim_dir_name)
        if sub_tags:
            is_sub_scene = True
        
        pos_length:int = len(scene_positions)
        for i in range(pos_length):
            scene_pos:dict[str,any] = scene_positions[i]
            pos_num:int = i
            ActorUtils.relax_creature_gender(scene_pos)
            TagsRepairer.fix_vampire_tags(scene_name, scene_tags, first_event_name, has_cre_vamplord)
            ActorUtils.process_pos_flag_futa_1(scene_tags, scene_pos, pos_length, pos_num, first_event_name)
            ActorUtils.process_pos_flag_sub(scene_tags, scene_pos, pos_num, sub_tags, is_sub_scene)
            ParamUtils.incorporate_slal_json_data(scene_name, scene_tags, scene_pos, [], 0, pos_num, 'Scene')
            ActorUtils.process_pos_flag_vampire(scene_tags, scene_pos, first_event_name)
            ActorUtils.process_pos_flag_futa_3(scene_tags, scene_pos, pos_length, pos_num)
            ActorUtils.process_pos_scaling(scene_name, scene_tags, scene_pos)

        TagsRepairer.fix_toys_tag(scene_tags, anim_obj_found)
        StageUtils.process_scene_furniture(scene_name, scene_tags, furniture, pos_length, anim_obj_found)

        # marks scenes as private (for manual conversion)
        if anim_dir_name == 'ZaZAnimsSLSB' or anim_dir_name == 'DDSL': #or anim_dir_name == 'EstrusSLSB'
            scene['private'] = True

        scene['tags'] = scene_tags
        #-----------------

    @staticmethod
    def edit_slsb_json(out_dir):
        for filename in os.listdir(Arguments.temp_dir):
            path = os.path.join(Arguments.temp_dir, filename)
            if os.path.isdir(path):
                continue

            anim_dir_name:str = ''
            if filename.endswith('.slsb.json'):
                base_name = filename.removesuffix(".slsb.json")
                if base_name in StoredData.cached_variables:
                    anim_dir_name = (StoredData.cached_variables[base_name]['anim_dir_name'])

            Arguments.debug('editing slsb', filename)
            data = None
            with open(path, 'r') as f:
                data = json.load(f)
                data['pack_author'] = Arguments.author
                
                pack_data_old = {}
                scenes_old = {}
                if data['pack_name'] in StoredData.slsb_jsons_data:
                    pack_data_old = StoredData.slsb_jsons_data[data['pack_name']]
                    scenes_old = pack_data_old['scenes']
                    data['prefix_hash'] = pack_data_old['pack_hash']
                    if data['pack_author'] == 'Unknown':
                        data['pack_author'] = pack_data_old['pack_author']

                new_scenes = {}
                scenes = data['scenes']
                sorted_scene_items = sorted(scenes.items(), key=lambda item: item[1].get('name', ''))

                for id, scene, in sorted_scene_items:
                    for item in scenes_old:
                        if scene['name'] == scenes_old[item]['scene_name']:
                            scene['id'] = scenes_old[item]['scene_hash']
                    new_scenes[scene['id']] = scene

                    StageProcessor.process_scene(scene, anim_dir_name, out_dir)

                data['scenes'] = new_scenes

            edited_path = Arguments.temp_dir + '/edited/' + filename
            with open(edited_path, 'w') as f:
                json.dump(data, f, indent=2)

#############################################################################################
class ConvertUtils:

    @staticmethod
    def execute_slsb_parsers():
        if Arguments.slsb_json_path is not None:
            Arguments.debug("\n--> PARSING SLSB JSON PROJECTS")
            for filename in os.listdir(Arguments.slsb_json_path):
                path = os.path.join(Arguments.slsb_json_path, filename)
                if os.path.isfile(path) and filename.lower().endswith(".slsb.json"):
                    with open(path, "r") as file:
                        Parsers.parse_slsb_jsons(file)

        if Arguments.slate_path is not None:
            Arguments.debug("--> PARSING SLATE ACTION_LOGS")
            for filename in os.listdir(Arguments.slate_path):
                path = os.path.join(Arguments.slate_path, filename)
                if os.path.isfile(path) and filename.lower().endswith('.json') \
                    and (filename.lower().startswith('slate_actionlog') or filename.lower().startswith('hentairim')):
                    StoredData.cached_variables['action_logs_found'] = True
                    with open(path, "r") as file:
                        Parsers.parse_slate_actionlogs(file)

    @staticmethod
    def execute_slal_parsers(working_dir):
        slal_jsons_dir = working_dir + '\\SLAnims\\json'
        slal_source_dir = working_dir + '\\SLAnims\\source'
        slal_fnislists_dir = working_dir + '\\meshes\\actors'

        if os.path.exists(slal_jsons_dir):
            Arguments.debug("---------> PARSING SLAL JSON FILES")
            for filename in os.listdir(slal_jsons_dir):
                path = os.path.join(slal_jsons_dir, filename)
                if os.path.isfile(path) and filename.lower().endswith(".json"):
                    with open(path, "r") as file:
                        Parsers.parse_slal_json(file)

        if os.path.exists(slal_source_dir):
            Arguments.debug("---------> PARSING SLAL SOURCE TXTs")
            for filename in os.listdir(slal_source_dir):
                path = os.path.join(slal_source_dir, filename)
                if os.path.isfile(path) and filename.lower().endswith(".txt"):
                    with open(path, "r") as file:
                        Parsers.parse_source_txt(file)

        if os.path.exists(slal_fnislists_dir):
            Arguments.debug("---------> PARSING SLAL FNIS LISTS")
            for item in os.listdir(slal_fnislists_dir):
                path = os.path.join(slal_fnislists_dir, item)
                if os.path.isdir(path):
                    ConvertUtils.iter_fnis_lists(path,'',Parsers.parse_slal_fnislists)    

    @staticmethod
    def iter_fnis_lists(dir, _dir, func):
        anim_dir = os.path.join(dir, 'animations')
        if os.path.exists(anim_dir) and os.path.exists(os.path.join(dir, 'animations')):
            for filename in os.listdir(anim_dir):
                path = os.path.join(anim_dir, filename)
                if os.path.isdir(path):
                    for filename in os.listdir(path):
                        if filename.startswith('FNIS_') and filename.endswith('_List.txt'):
                            func(path, _dir, filename)
        elif os.path.isdir(dir):
            for filename in os.listdir(dir):
                path = os.path.join(dir, filename)
                ConvertUtils.iter_fnis_lists(path, _dir, func)

    @staticmethod
    def build_behaviour(parent_dir, out_dir, list_name):
        list_path = os.path.join(parent_dir, list_name)
        if '_canine' in list_name.lower():
            return
        behavior_file_name = list_name.lower().replace('fnis_', '')
        behavior_file_name = behavior_file_name.lower().replace('_list.txt', '')
        behavior_file_name = 'FNIS_' + behavior_file_name + '_Behavior.hkx'
        Arguments.debug('generating', behavior_file_name)

        cwd = os.getcwd()
        os.chdir(Arguments.fnis_path)
        output = subprocess.Popen(f"./commandlinefnisformodders.exe \"{list_path}\"", stdout=subprocess.PIPE).stdout.read()
        os.chdir(cwd)

        out_path_parts = os.path.normpath(list_path).split(os.sep)
        
        start_index = -1
        end_index = -1

        for i in range(len(out_path_parts) - 1, -1, -1):
            split = out_path_parts[i].lower()

            if split == 'meshes':
                start_index = i
            elif split == 'animations':
                end_index = i

        behaviour_folder = 'behaviors' if '_wolf' not in list_name.lower() else 'behaviors wolf'
        behaviour_path = os.path.join(Arguments.skyrim_path, 'data', *out_path_parts[start_index:end_index], behaviour_folder, behavior_file_name)

        if os.path.exists(behaviour_path):
            out_behavior_dir = os.path.join(out_dir, *out_path_parts[start_index:end_index], behaviour_folder)
            out_behaviour_path = os.path.join(out_behavior_dir, behavior_file_name)
            os.makedirs(out_behavior_dir, exist_ok=True)
            if os.path.exists(out_behaviour_path):
                os.remove(out_behaviour_path)
            shutil.move(behaviour_path, out_behaviour_path)

        if Arguments.remove_anims:
            StoredData.anim_cleanup_dirs.add(parent_dir)

    @staticmethod
    def do_remove_anims(parent_dir):
        for filename in os.listdir(parent_dir):
            if os.path.splitext(filename)[1].lower() == '.hkx':
                os.remove(os.path.join(parent_dir, filename))
        if parent_dir.endswith("EstrusSLSB"):
            base_dir = os.path.dirname(parent_dir)
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if item == "EstrusSLSB":
                    continue
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

#############################################################################################
class ConvertMain:

    @staticmethod
    def do_convert_single(parent_dir, dir):
        working_dir = os.path.join(parent_dir, dir)
        out_dir = os.path.join(Path(parent_dir).parent, 'SLSB_Outputs', 'conversions '+Keywords.TIMESTAMP, dir)

        if os.path.exists(Arguments.temp_dir):
            shutil.rmtree(Arguments.temp_dir)
        os.makedirs(Arguments.temp_dir + '/edited')
        os.makedirs(out_dir + '/SKSE/Sexlab/Registry/Source')

        StoredData.reset_stored_data()
        ConvertUtils.execute_slal_parsers(working_dir)
        Editors.fix_slal_jsons(working_dir)

        Arguments.debug("---------> CONVERTING SLAL TO SLSB PROJECTS")
        slal_jsons_dir = working_dir + '\\SLAnims\\json'
        for filename in os.listdir(slal_jsons_dir):
            path = os.path.join(slal_jsons_dir, filename)
            if os.path.isfile(path) and filename.lower().endswith(".json"):
                Arguments.debug('converting', filename)
                output = subprocess.Popen(f"{Arguments.slsb_path} convert --in \"{path}\" --out \"{Arguments.temp_dir}\"", stdout=subprocess.PIPE).stdout.read()

        Arguments.debug("---------> EDITING OUTPUT SLSB PROJECTS")
        StageProcessor.edit_slsb_json(out_dir)
        # Building SLRs for edited SLSB Project
        for filename in os.listdir(Arguments.temp_dir):
            path = os.path.join(Arguments.temp_dir, filename)
            if os.path.isdir(path):
                continue
            edited_path = Arguments.temp_dir + '/edited/' + filename
            output = subprocess.Popen(f"{Arguments.slsb_path} build --in \"{edited_path}\" --out \"{out_dir}\"", stdout=subprocess.PIPE).stdout.read()
            shutil.copyfile(edited_path, out_dir + '/SKSE/Sexlab/Registry/Source/' + filename)

        slsb_fnis_list_dir = out_dir + '\\meshes\\actors'
        ConvertUtils.iter_fnis_lists(slsb_fnis_list_dir,'', Editors.edit_output_fnis)
        if not Arguments.no_build and Arguments.fnis_path is not None:
            Arguments.debug("---------> BUILDING FNIS BEHAVIOUR")
            ConvertUtils.iter_fnis_lists(slsb_fnis_list_dir, out_dir, ConvertUtils.build_behaviour)

        shutil.rmtree(Arguments.temp_dir)
        if Arguments.remove_anims:
            for d in StoredData.anim_cleanup_dirs:
                ConvertUtils.do_remove_anims(d)


    @staticmethod
    def do_convert_bulk():
        for dir_name in os.listdir(Arguments.parent_dir):
            if dir_name.startswith("!"):
                continue
            dir_path = os.path.join(Arguments.parent_dir, dir_name)
            if os.path.isdir(dir_path):
                slal_dir_default = os.path.join(dir_path, 'SLAnims')            
                if os.path.exists(slal_dir_default):
                    Arguments.debug('\n\033[92m' + "============== PROCESSING " + dir_name + " ==============" + '\033[0m')
                    ConvertMain.do_convert_single(Arguments.parent_dir, dir_name)

    @staticmethod
    def check_wrong_dir_structure():
        slal_dir_outside = os.path.join(Arguments.parent_dir, 'SLAnims')
        if os.path.exists(slal_dir_outside):
            Arguments.debug('\033[91m' + "[ERROR] Found 'SLAnims' folder directly inside the provided path. No packs outside a sub-directory will be processed for conversion." + '\033[0m')
            Arguments.debug('\033[92m' + "[SOLUTION] Each SLAL pack has to be in its own sub-directory, even when converting a single pack." + '\033[0m')
        misplaced_slal_packs = []
        for item in os.listdir(Arguments.parent_dir):
            if item.startswith("!"):
                continue
            item_path = os.path.join(Arguments.parent_dir, item)
            if os.path.isdir(item_path):
                slal_dir_default = os.path.join(item_path, 'SLAnims')            
                if not os.path.exists(slal_dir_default):
                    for sub_item in os.listdir(item_path):
                        sub_item_path = os.path.join(item_path, sub_item)
                        if os.path.isdir(sub_item_path):
                            slal_dir_inside = os.path.join(sub_item_path, 'SLAnims')
                            if os.path.exists(slal_dir_inside):
                                misplaced_slal_packs.append(sub_item_path)
        if misplaced_slal_packs:
            Arguments.debug('\n\033[93m' + "[WARNING] Found at least one sub-directory having a standalone SLAL pack inside a sub-directory in the provided path. The pack in this sub-sub-directory will not be processed for conversion." + '\033[0m')
            for entry in misplaced_slal_packs:
                Arguments.debug(f"- {entry}")
            Arguments.debug('\033[92m' + "SOLUTION: If you want these packs to also be processed for conversion, make sure they appear as direct sub-directories inside the provided path." + '\033[0m')

#############################################################################################
class PostConversion: # HANDLES XMLs WITH SPACES (FOR ANUBS AND BAKA PACKS)

    @staticmethod
    def replicate_structure(source_dir, required_structure):
        for root, _, files in os.walk(source_dir):
            for file in files:
                source_path = os.path.join(root, file)

                req_paths = []
                for dest_root, dirs, dest_files in os.walk(required_structure):
                    #dirs[:] = [d for d in dirs if d.lower() != "conversion"]
                    if file in dest_files:
                        req_paths.append(os.path.join(dest_root, file))

                if len(req_paths) > 1:
                    Arguments.debug(f"\033[93m---> {len(req_paths)} instances found for {file}:\033[0m")
                    Arguments.debug(req_paths)
                    Arguments.debug("\033[93mScript is handling this, but it's undesirable. Make sure the directory with SLAL packs is not polluted. It can also hint at packaging issues by animators.\033[0m")

                while req_paths:
                    req_path = req_paths.pop(0)
                    req_subdir = os.path.relpath(req_path, required_structure)
                    source_structure = os.path.join(source_dir, req_subdir)

                    os.makedirs(os.path.dirname(source_structure), exist_ok=True)
                    if req_paths:
                        shutil.copy2(source_path, source_structure)
                    else:
                        shutil.move(source_path, source_structure)

    @staticmethod
    def move_with_replace(source_dir, target_dir):
        if os.path.isdir(target_dir):
            for item in os.listdir(source_dir):
                source_item = os.path.join(source_dir, item)
                target_item = os.path.join(target_dir, item)

                if os.path.isfile(source_item):
                    if os.path.isfile(target_item):
                        os.remove(target_item)
                    shutil.move(source_item, target_item)
                    
                elif os.path.isdir(source_item):
                    if not os.path.isdir(target_item):
                        os.makedirs(target_item)
                    PostConversion.move_with_replace(source_item, target_item)

            if not os.listdir(source_dir):
                os.rmdir(source_dir)

    @staticmethod
    def reattempt_behaviour_gen():
        if Arguments.tmp_log_dir is None:
            return
        for f in os.listdir(Arguments.tmp_log_dir):
            if f.lower().endswith(".xml") and " " in f:
                StoredData.xml_with_spaces.append(f)
        if StoredData.xml_with_spaces == []:
            return
        
        Arguments.debug("\n======== PROCESSING XMLs_WITH_SPACES ========")
        tmp_xml_subdir = os.path.join(Arguments.tmp_log_dir, "xml")
        tmp_hkx_subdir = os.path.join(Arguments.tmp_log_dir, "hkx")
        os.makedirs(tmp_xml_subdir, exist_ok=True)
        os.makedirs(tmp_hkx_subdir, exist_ok=True)

        Arguments.debug("---------> segregating XMLs with spaces in names")
        for filename in os.listdir(Arguments.tmp_log_dir):
            path = os.path.join(Arguments.tmp_log_dir, filename)
            if os.path.isfile(path) and filename.lower().endswith(".xml") and " " in filename:
                Arguments.debug(filename)
                new_path = os.path.join(tmp_xml_subdir, filename)
                shutil.move(path, new_path)

        Arguments.debug("---------> converting XMLs to HKXs")
        for xml_file in os.listdir(tmp_xml_subdir):
            if xml_file.lower().endswith(".xml"):
                hkxcmd_path = os.path.join(Arguments.fnis_path, "hkxcmd.exe")
                input_path = os.path.join(tmp_xml_subdir, xml_file)
                output_file = os.path.splitext(xml_file)[0] + ".hkx"
                output_path = os.path.join(tmp_hkx_subdir, output_file)
                command = [hkxcmd_path, "convert", "-v:amd64", os.path.normpath(input_path), os.path.normpath(output_path)]
                try:
                    subprocess.run(command, check=True)
                except:
                    Arguments.debug(f"Failed to convert: {xml_file}")

        Arguments.debug("---------> replicating source structure; stay patient...")
        PostConversion.replicate_structure(tmp_hkx_subdir, Arguments.parent_dir)
        Arguments.debug("---------> incorporating converted HKXs")
        conversions_dir = os.path.join(Path(Arguments.parent_dir).parent, 'SLSB_Outputs', 'conversions '+Keywords.TIMESTAMP)
        PostConversion.move_with_replace(tmp_hkx_subdir, conversions_dir)
        
        #reset tmp_logs_dir
        shutil.rmtree(Arguments.tmp_log_dir)
        os.makedirs(Arguments.tmp_log_dir, exist_ok=True)

#############################################################################################
def execute_script():
    start_time = time.time()
    Arguments.process_arguments()
    ConvertUtils.execute_slsb_parsers()
    ConvertMain.do_convert_bulk()
    ConvertMain.check_wrong_dir_structure()
    PostConversion.reattempt_behaviour_gen()
    end_time = time.time()
    elapsed = end_time - start_time
    Arguments.debug(f'\n<<<<<<<<<<<<<<< COMPLETED SUCCESSFULLY (in {elapsed:.4f}s) >>>>>>>>>>>>>>>')

execute_script()