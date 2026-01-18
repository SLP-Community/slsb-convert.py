# Script Version: 1.1 (to be used with SLSB v2.0.0+)
from typing import ClassVar, Iterable, TextIO
from datetime import datetime
from pprint import pprint
from pathlib import Path
import subprocess
import argparse
import shutil
import json
import time
import re

class Arguments:

    #required
    slsb_path:Path|None = None          # path to slsb.exe
    parent_dir:Path|None = None         # path to dir containing slal packs/modules
    #recommended
    skyrim_path:Path|None = None        # path to `basegame_replica` directory
    remove_anims:bool = False           # True cleans up HKXs copied for behavior gen
    no_build:bool = False               # True skips building behaviour HKX files
    #public_release
    slate_path:Path|None = None         # path to slate action logs
    slsb_json_path:Path|None = None     # path to latest slsb project, for updates
    #optional
    stricter_futa:bool = False          # True skips assigning futa for positions with strap_on
    author:str|None = None              # name of the pack/conversion author
    #auto_determined
    fnis_path:Path|None = None          # path to fnis for modders
    tmp_log_dir:Path|None = None        # path to generated XMLs
    temp_dir:Path|None = None           # for editing slsb json

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
        Arguments.slsb_path = Path(args.slsb).resolve()
        Arguments.parent_dir = Path(args.parent).resolve()
        Arguments.skyrim_path = Path(args.skyrim).resolve() if args.skyrim else None
        Arguments.slate_path = Path(args.slate).resolve() if args.slate else None
        Arguments.slsb_json_path = Path(args.update).resolve() if args.update else None
        Arguments.remove_anims = args.remove_anims
        Arguments.no_build = args.no_build
        Arguments.stricter_futa = args.stricter_futa
        Arguments.author = args.author or 'Unknown'
        Arguments.temp_dir = Arguments.slsb_path.parent/'tmp_slsb_dir'
        if args.skyrim:
            Arguments.fnis_path = Arguments.skyrim_path/'Data'/'tools'/'GenerateFNIS_for_Modders'
            Arguments.tmp_log_dir = Arguments.fnis_path/'temporary_logs'

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
    ANIM_PREFIX_PATTERN = re.compile(r'^\s*anim_name_prefix\("([^"]*)"\)', re.IGNORECASE)
    DIR_NAME_PATTERN = re.compile(r'anim_dir\("([^"]*)"\)', re.IGNORECASE)
    ANIM_START_PATTERN = re.compile(r'^\s*Animation\(', re.IGNORECASE)
    ANIM_END_PATTERN = re.compile(r'^\s*\)', re.IGNORECASE)
    ID_VALUE_PATTERN = re.compile(r'id="([^"]*)"', re.IGNORECASE)
    NAME_VALUE_PATTERN = re.compile(r'name="([^"]*)"', re.IGNORECASE)
    ACTOR_PATTERN = re.compile(r'actor\s*(\d+)\s*=\s*([^()]+)\(([^)]*)\)', re.IGNORECASE)
    BIGGUY_PATTERN = re.compile(r'(base\s?scale)\s?(\d+\.\d+)', re.IGNORECASE)
    SCALING_PATTERN = re.compile(r'(set\s?scale)\s?(\d+(?:\.\d+)?)?', re.IGNORECASE)
    FNIS_LIST_PATTERN = re.compile(r'^fnis_(.*)_list\.txt$', re.IGNORECASE)

#############################################################################################
class StoredData:

    #session-specific mutables
    slsb_jsons_data:ClassVar[dict] = {}
    slate_logs_data:ClassVar[list] = []
    cached_variables:ClassVar[dict] = {'action_logs_found': False} # also stores {'slal_json_filename': anim_dir_name}
    xml_with_spaces:ClassVar[list[str]|str] = []
    processed_slal_modules:ClassVar[set] = set()
    #pack-specific mutables
    slal_jsons_data:ClassVar[dict] = {}
    source_txts_data:ClassVar[dict] = {}
    slal_fnislists_data:ClassVar[dict] = {}
    unique_animlist_options:ClassVar[dict] = {}
    anim_cleanup_dirs:ClassVar[set] = set()
    created_hardlinks:ClassVar[list[str]|str] = []
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
        StoredData.created_hardlinks.clear()

#############################################################################################
class TagUtils:

    @staticmethod
    def if_any_found(tags:list[str], _any:list[str]|str, *extra_any:Iterable) -> bool:
        if isinstance(_any, str): _any = [_any]
        if isinstance(extra_any, str): extra_any = [extra_any]
        tags_str:str = ";".join(tags)
        if any(k in tags_str for k in _any):
            return True
        for extra_check in extra_any:
            extra_str: str = ";".join(map(str, extra_check))
            if any(k in extra_str for k in _any):
                return True
        return False
    @staticmethod
    def if_then_add(tags:list[str], lookup:list[str]|str, _any:list[str]|str, not_any:list[str]|str, add:str):
        if add not in tags and TagUtils.if_any_found(tags, _any, lookup) and (not not_any or not TagUtils.if_any_found(tags, not_any)):
            tags.append(add)
    @staticmethod
    def if_in_then_add(tags:list[str], _list:list[str], _any:list[str]|str, add:str):
        if add not in tags and TagUtils.if_any_found(_list, _any):
            tags.append(add)
    @staticmethod
    def if_then_remove(tags:list[str], all_in_tags:list[str], any_not_in_tags:list[str], remove:str):
        if remove in tags and all(item in tags for item in all_in_tags) and not TagUtils.if_any_found(tags, any_not_in_tags):
            tags.remove(remove)
    @staticmethod
    def if_then_replace(tags:list[str], remove:str, add:str):
        if remove in tags:
            tags.remove(remove)
            if add not in tags:
                tags.append(add)
    @staticmethod
    def bulk_add(tags:list[str], add:list[str]|str):
        if isinstance(add, str):
            add = [add]
        for item in add:
            if item and item not in tags:
                tags.append(item)
    @staticmethod
    def bulk_remove(tags:list[str], remove:list[str]|str):
        if isinstance(remove, str):
            remove = [remove]
        for item in remove:
            if item in tags:
                tags.remove(item)
    @staticmethod
    def remove_similar(tags: list[str]):
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                unique_tags.append(tag)
                seen.add(tag)
        tags[:] = unique_tags

#############################################################################################
class TagsRepairer:

    @staticmethod
    def update_scene_tags(scene_name:str, tags:list[str], anim_dir_name:str, event_name:str):
        lookup:list[str] = [scene_name.lower(), anim_dir_name.lower(), event_name.lower()]
        # tags corrections
        TagUtils.if_then_add(tags,lookup, ['laying'], ['eggs', 'egg'], 'lying')
        TagUtils.if_then_remove(tags, ['laying', 'lying'], ['eggs', 'egg'], 'laying')
        TagUtils.if_then_replace(tags, 'invfurn', 'invisfurn')
        TagUtils.if_then_replace(tags, 'invisible obj', 'invisfurn')
        TagUtils.if_then_replace(tags, 'cunnilingius', 'cunnilingus')
        TagUtils.if_then_replace(tags, 'agressive', 'aggressive')
        TagUtils.if_then_replace(tags, 'femodm', 'femdom')
        # furniture tags
        TagUtils.if_then_add(tags,lookup, ['inv'], '', 'invisfurn')
        TagUtils.if_then_add(tags,lookup, Keywords.FURNITURE, '', 'furniture')
        TagUtils.if_then_remove(tags, ['invisfurn', 'furniture'], '', 'furniture')
        # unofficial standardization
        TagUtils.if_then_add(tags,lookup, ['femdom', 'amazon', 'cowgirl', 'femaledomination', 'female domination', 'leito xcross standing'], '', 'femdom')
        TagUtils.if_then_add(tags,lookup, ['basescale', 'base scale', 'setscale', 'set scale', 'bigguy', 'bigman'], '', 'scaling')
        TagUtils.if_then_add(tags,lookup, Keywords.FUTA, '', 'futa')
        TagUtils.bulk_remove(tags, ['vampire', 'vampirelord']) # will be added later after special checks
        # official standard tags
        TagUtils.if_then_add(tags,lookup, ['mage', 'staff', 'alteration', 'rune', 'magicdildo', 'magic'], '', 'magic')
        TagUtils.if_then_add(tags,lookup, ['dp', 'doublepen'], '', 'doublepenetration')
        TagUtils.if_then_add(tags,lookup, ['tp', 'triplepen'], '', 'triplepenetration')
        TagUtils.if_then_add(tags,lookup, ['guro', 'execution'], '', 'gore')
        TagUtils.if_then_add(tags,lookup, ['choke', 'choking'], '', 'asphyxiation')
        TagUtils.if_then_add(tags,lookup, ['titfuck', 'tittyfuck'], '', 'boobjob')
        TagUtils.if_then_add(tags,lookup, ['trib', 'tribbing'], '', 'tribadism')
        TagUtils.if_then_add(tags,lookup, ['doggystyle', 'doggy'], '', 'doggy')
        TagUtils.if_then_add(tags,lookup, ['facesit'], '', 'facesitting')
        TagUtils.if_then_add(tags,lookup, ['lotus'], '', 'lotusposition')
        TagUtils.if_then_add(tags,lookup, ['spank'], '', 'spanking')
        TagUtils.if_then_add(tags,lookup, ['rimjob'], '', 'rimming')
        TagUtils.if_then_add(tags,lookup, ['kiss'], '', 'kissing')
        TagUtils.if_then_add(tags,lookup, ['hold'], '', 'holding')
        TagUtils.if_then_add(tags,lookup, ['69'], '', 'sixtynine')
        TagUtils.remove_similar(tags)
        TagUtils.bulk_remove(tags, '')

    @staticmethod
    def fix_submissive_tags(scene_name:str, scene_tags:list[str], anim_dir_name:str) -> None:
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
        if TagUtils.if_any_found(scene_tags, Keywords.UNCONSCIOUS, s,d):
            sub_tags['unconscious'] = True
        if TagUtils.if_any_found(scene_tags, ['guro', 'gore'], s,d): 
            sub_tags['gore'] = True
        if TagUtils.if_any_found(scene_tags, ['amputee'], s,d): 
            sub_tags['amputee'] = True
        if TagUtils.if_any_found(scene_tags, ['nya', 'molag', 'psycheslavepunishment'], s,d): 
            sub_tags['ryona'] = True
        if TagUtils.if_any_found(scene_tags, ['humiliation', 'punishment'], s,d): 
            sub_tags['humiliation'] = True
        if TagUtils.if_any_found(scene_tags, ['asphyxiation'], s,d): 
            sub_tags['asphyxiation'] = True
        if TagUtils.if_any_found(scene_tags, ['spanking'], s,d): 
            sub_tags['spanking'] = True
        if TagUtils.if_any_found(scene_tags, Keywords.DOMINANT, s,d):
            sub_tags['dominant'] = True
        # extensive treatment of forced scenes
        if TagUtils.if_any_found(scene_tags, Keywords.FORCED, s,d):
            sub_tags['forced'] = True
        if 'aggressive' in scene_tags:
            if TagUtils.if_any_found(scene_tags, Keywords.USES_ONLY_AGG_TAG, s,d):
                sub_tags['forced'] = True
        # adjust stage tags based on sub_flags
        subtags_found:list[str] = []
        for sub_tag, flag_value in sub_tags.items():
            if flag_value:
                subtags_found.append(sub_tag)
                if sub_tag not in scene_tags:
                    scene_tags.append(sub_tag)
            elif not flag_value and sub_tag in scene_tags:
                scene_tags.remove(sub_tag)
        return subtags_found

    @staticmethod
    def fix_leadin_tag(scene_tags:list[str]):
        TagUtils.if_then_remove(scene_tags, ['leadin'], '', 'leadin')
        if any(kwd in scene_tags for kwd in Keywords.LEADIN) and all(kwd not in scene_tags for kwd in Keywords.NOT_LEADIN):
            TagUtils.bulk_add(scene_tags, 'leadin')

    @staticmethod
    def fix_vampire_tags(scene_name:str, scene_tags:list[str], event_name:str, has_cre_vamplord:bool):
        if has_cre_vamplord:
            TagUtils.bulk_add(scene_tags, 'vampirelord')
        elif 'vamp' in event_name or 'vamp' in scene_name.lower():
            TagUtils.bulk_add(scene_tags, 'vampire')

    @staticmethod
    def fix_toys_tag(scene_tags:list[str], anim_obj_found:bool):
        if not anim_obj_found:
            TagUtils.bulk_remove(scene_tags, 'toys')
        else:
            TagUtils.bulk_add(scene_tags, 'toys')

#############################################################################################
class SLATE:

    @staticmethod
    def insert_slate_tags(scene_name:str, scene_tags:list[str]|str, ):
        if StoredData.cached_variables["action_logs_found"]:
            TagToAdd = ''
            TagToRemove = ''
            for entry in StoredData.slate_logs_data:
                if scene_name.lower() == entry['anim'].lower():
                    if entry['action'].lower() == 'addtag':
                        TagToAdd = entry['tag'].lower()
                        if TagToAdd not in scene_tags:
                            scene_tags.append(TagToAdd)
                    elif entry['action'].lower() == 'removetag':
                        TagToRemove = entry['tag'].lower()
                        if TagToRemove in scene_tags:
                            scene_tags.remove(TagToRemove)

    @staticmethod
    def check_hentairim_tags(scene_tags:list[str], stage_tags:list[str], stage_num:int, pos_ind:str) -> None:
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
        tags_set = set(scene_tags)
        rimtags_found:list[str] = []
        for entry, dynamic_tag in rimtags.items():
            static_tag = dynamic_tag.format(stage=stage_num, pos=pos_ind)
            if static_tag in tags_set:
                rimtags_found.append(entry)
                # ensure stage-specifiicity for rim-tags
                TagUtils.bulk_remove(scene_tags, static_tag)
                TagUtils.bulk_add(stage_tags, static_tag)
        return rimtags_found

    @staticmethod
    def implement_hentairim_tags(scene_tags:list[str], stage_tags:list[str], rimtags:list[str]):
        TagUtils.bulk_add(scene_tags, ['rimtagged'])
        # removes all stage tags that would be added by HentaiRim
        TagUtils.bulk_remove(scene_tags, [Keywords.HENTAIRIM_TAGS, 'leadin'])
        # each stage tagged differently based on HentaiRim interactions
        TagUtils.if_in_then_add(stage_tags, rimtags, ['sst', 'fst', 'bst'], 'stimulation')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['kis'], 'kissing')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['shj', 'fhj'], 'handjob')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['sfj', 'ffj'], 'footjob')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['stf', 'ftf'], 'boobjob')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['sbj', 'fbj', 'smf', 'fmf'], 'blowjob')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['cun'], 'cunnilingus')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['sbj', 'fbj', 'smf', 'fmf', 'cun'], 'oral')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['scg', 'fcg', 'sac', 'fac'], 'cowgirl')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['svp', 'fvp', 'sdv', 'fdv', 'scg', 'fcg', 'sdp', 'fdp'], 'vaginal')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['sap', 'fap', 'sda', 'fda', 'sac', 'fac', 'sdp', 'fdp'], 'anal')
        if 'blowjob' in stage_tags:
            TagUtils.if_then_add(stage_tags,'', 'vaginal', 'anal', 'spitroast')
            TagUtils.if_then_add(stage_tags,'', 'anal', 'vaginal', 'spitroast')
            TagUtils.if_then_add(stage_tags,'', ['vaginal', 'anal'], '', 'triplepenetration')
        if 'sdp' in rimtags or 'fdp' in rimtags:
            TagUtils.bulk_add(stage_tags, 'doublepenetration')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['fst','bst','fvp','fap','fcg','fac','fdp','fdv','fda','fhj','ftf','fmf','ffj','fbj'], 'rimfast')
        TagUtils.if_in_then_add(stage_tags, rimtags, ['sst','svp','sap','scg','sac','sdp','sdv','sda','shj','stf','smf','sfj','kis','cun','sbj'], 'rimslow')
        if not TagUtils.if_any_found(stage_tags, Keywords.HENTAIRIM_TAGS):
            TagUtils.bulk_add(stage_tags, 'leadin')

    @staticmethod
    def check_asl_tags(scene_tags:list[str], stage_tags:list[str], stage_num:int) -> None:
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
        tags_set = set(scene_tags)
        asltags_found:list[str] = []
        for entry, dynamic_tag in asltags.items():
            static_tag = dynamic_tag.format(stage=stage_num)
            if static_tag in tags_set:
                asltags_found.append(entry)
                # ensure stage-specifiicity for asl-tags
                TagUtils.bulk_remove(scene_tags, static_tag)
                TagUtils.bulk_add(stage_tags, static_tag)
        return asltags_found

    @staticmethod
    def implement_asl_tags(scene_tags:list[str], stage_tags:list[str], asltags:list[str]):
        # stores info on vaginal/anal tag presence (for spitroast)
        TagUtils.if_then_add(scene_tags,'', 'anal', 'vaginal', 'sranaltmp')
        TagUtils.if_then_add(scene_tags,'', 'vaginal', 'anal', 'srvagtmp')
        # removes all scene tags that would be added by ASL
        TagUtils.bulk_remove(scene_tags, ['leadin', 'oral', 'vaginal', 'anal', 'spitroast', 'doublepenetration', 'triplepenetration'])
        if not 'rimtagged' in scene_tags:
            # each stage tagged differently based on ASL interactions
            TagUtils.if_in_then_add(stage_tags, asltags, ['li'], 'leadin')
            TagUtils.if_in_then_add(stage_tags, asltags, ['sb', 'fb'], 'oral')
            TagUtils.if_in_then_add(stage_tags, asltags, ['sv', 'fv'], 'vaginal')
            TagUtils.if_in_then_add(stage_tags, asltags, ['sa', 'fa'], 'anal')
            if 'sr' in asltags:
                TagUtils.bulk_add(stage_tags, ['spitroast', 'oral'])
                TagUtils.if_in_then_add(stage_tags, scene_tags, ['sranaltmp'], 'anal')
                TagUtils.if_in_then_add(stage_tags, scene_tags, ['srvagtmp'], 'vaginal')
            if 'dp' in asltags:
                TagUtils.bulk_add(stage_tags, ['doublepenetration', 'vaginal', 'anal'])
            if 'tp' in asltags:
                TagUtils.bulk_add(stage_tags, ['triplepenetration', 'oral', 'vaginal', 'anal'])
            TagUtils.if_in_then_add(stage_tags, asltags, ['sb','sv','sa'], 'rimslow')
            TagUtils.if_in_then_add(stage_tags, asltags, ['fb','fv','fa'], 'rimfast')
        TagUtils.bulk_remove(scene_tags, ['sranaltmp', 'srvagtmp'])

    @staticmethod
    def correct_aslsfx_tags(scene_tags:list[str], stage_tags:list[str],  stage_num:int):
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
        tags_set = set(scene_tags)
        for entry, dynamic_tag in aslsfx_tags.items():
            static_tag = dynamic_tag.format(stage=stage_num)
            if static_tag in tags_set:
                # ensure stage-specifiicity for asl-sfx-tags
                TagUtils.bulk_remove(scene_tags, static_tag)
                TagUtils.bulk_add(stage_tags, static_tag)

    @staticmethod
    def implement_position_tags(pos_tags:list[str]):
        TagUtils.if_then_add(pos_tags,'', 'ldi', '', 'LeadIn')
        TagUtils.if_then_add(pos_tags,'', 'kis', '', 'bKissing')
        TagUtils.if_then_add(pos_tags,'', ['sst', 'fst', 'bst'], '', 'pStimulation')
        TagUtils.if_then_add(pos_tags,'', ['shj', 'fhj'], '', 'pHandJob')
        TagUtils.if_then_add(pos_tags,'', ['sfj', 'ffj'], '', 'pFootJob')
        TagUtils.if_then_add(pos_tags,'', ['stf', 'ftf'], '', 'pBoobJob')
        TagUtils.if_then_add(pos_tags,'', ['cun', 'sbj', 'fbj'], '', 'aOral')
        TagUtils.if_then_add(pos_tags,'', ['smf', 'fmf'], '', 'pOral')
        TagUtils.if_then_add(pos_tags,'', ['sdv', 'fdv'], '', 'aVaginal')
        TagUtils.if_then_add(pos_tags,'', ['svp', 'fvp', 'scg', 'fcg', 'sdp', 'fdp'], '', 'pVaginal')
        TagUtils.if_then_add(pos_tags,'', ['sda', 'fda'], '', 'aAnal')
        TagUtils.if_then_add(pos_tags,'', ['sap', 'fap', 'sac', 'fac', 'sdp', 'fdp'], '', 'pAnal')
    @staticmethod
    def implement_slate_tags(scene_tags:list[str], stage_tags:list[str], stage_num:int, stage_positions:list[dict]):
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
                stage_pos_rimtags:list[str] = SLATE.check_hentairim_tags(scene_tags, stage_tags, stage_num, pos_ind)
                if stage_pos_rimtags:
                    TagUtils.bulk_add(rimtags, stage_pos_rimtags)
                    # rim_pos_tags (position specific tags)
                    TagUtils.bulk_add(tmp_stage_pos['tags'], stage_pos_rimtags)  
                    SLATE.implement_position_tags(tmp_stage_pos['tags'])
            if rimtags:
                SLATE.implement_hentairim_tags(scene_tags, stage_tags, rimtags)
            asltags:list[str] = SLATE.check_asl_tags(scene_tags, stage_tags, stage_num)
            if asltags:
                SLATE.implement_asl_tags(scene_tags, stage_tags, asltags)
            SLATE.correct_aslsfx_tags(scene_tags, stage_tags, stage_num)

#############################################################################################
class Parsers:

    @staticmethod
    def parse_slal_json(data_stream:TextIO):
        parsed_json = json.load(data_stream)
        for scene_data in parsed_json.get('animations', []):
            scene_info = {
                'scene_name': scene_data.get('name'),
                'scene_id': scene_data.get('id'),
                'scene_tags': scene_data.get('tags').split(','),
                'scene_sound': scene_data.get('sound'),
                'actors': {},
                'stage_params': {}
            }
            for key, actor_data in enumerate(scene_data['actors'], 1):
                actor_key = f'a{key}'
                actor_info = {
                    'actor_key': actor_key,
                    'gender': actor_data['type'],
                    'add_cum': actor_data.get('add_cum', 0),
                    f'{actor_key}_stage_params': {}
                }
                for idx, actor_stage_data in enumerate(actor_data['stages'], 1):
                    actor_stage_params_key = f'Stage {idx}'
                    actor_stage_params_info = {
                        'actor_stage_params_key': actor_stage_params_key,
                        'stage_id': actor_stage_data.get('id'),
                        'open_mouth': actor_stage_data.get('open_mouth', 'False'),
                        'strap_on': actor_stage_data.get('strap_on', 'False'),
                        'silent': actor_stage_data.get('silent', 'False'),
                        'sos': actor_stage_data.get('sos', 0),
                        'up': actor_stage_data.get('up', 0),
                        'side': actor_stage_data.get('side', 0),
                        'rotate': actor_stage_data.get('rotate', 0),
                        'forward': actor_stage_data.get('forward', 0)
                    }
                    actor_info[f'{actor_key}_stage_params'][actor_stage_params_key] = actor_stage_params_info
                
                scene_info['actors'][actor_key] = actor_info
            
            for scene_stage_data in scene_data.get('stages', []):
                stage_params_key = f'Stage {scene_stage_data.get('number', 'None')}'
                
                scene_stage_params_info = {
                    'stage_params_key': stage_params_key,
                    'sound': scene_stage_data.get('sound', 'None'),
                    'timer': scene_stage_data.get('timer', 0)
                }
                scene_info['stage_params'][stage_params_key] = scene_stage_params_info

            StoredData.slal_jsons_data[scene_info['scene_name']] = scene_info

    @staticmethod
    def parse_slsb_jsons(data_stream:TextIO):
        parsed_json = json.load(data_stream)
        pack_info = {
            'pack_name': parsed_json.get('pack_name'),
            'pack_hash': parsed_json.get('prefix_hash'),
            'pack_author': parsed_json.get('pack_author'),
            'scenes': {}
        }
        for scene_id, scene_data in parsed_json.get('scenes', {}).items():
            scene_info = {
                'scene_hash': scene_data.get('id'),
                'scene_name': scene_data.get('name'),
                'scene_stages': {},
                'scene_root': scene_data.get('root'),
                'scene_graph': scene_data.get('graph')
            }
            for i, stage_data in enumerate(scene_data.get('stages', {})):
                extra = stage_data.get('extra')
                stage_info = {
                    'stage_hash': stage_data.get('id'),
                    'stage_name': stage_data.get('name'),
                    'navigation_text': extra.get('nav_text')
                }
                scene_info['scene_stages'][i] = stage_info

            pack_info['scenes'][scene_id] = scene_info

        if pack_info['pack_name']:
            StoredData.slsb_jsons_data[pack_info['pack_name']] = pack_info

    @staticmethod
    def parse_source_txt(data_stream:TextIO):
        inside_animation:bool = False
        anim_name_prefix:str = ''
        anim_full_name:str = ''

        for line in data_stream:
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
    def parse_slal_fnislists(list_parent_path:Path, list_name:str, list_out_path:Path|None):
        list_path:Path = list_parent_path/list_name
        lines = list_path.read_text(encoding='utf-8', errors='replace').splitlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("'"):
                continue
            splits = line.split()
            if not splits or splits[0].lower() in ('version', 'ï»¿version'):
                continue

            anim_file_name:str|None = None
            anim_event_name:str|None = None
            options:list[str] = []
            anim_objects:list[str] = []

            for i, split in enumerate(splits):
                if len(split) <= 1:
                    continue
                elif split.startswith('-'):
                    options_list = split[1:].split(',')
                    for item in options_list:
                        if item.lower() not in ('avbhumanoidfootikdisable', 'tn', 'o', 'a', 'md') and item not in options:
                            options.append(item)
                elif '.hkx' in split.lower():
                    anim_file_name = splits[i]
                    anim_event_name = splits[i-1].lower()
                else:
                    if anim_event_name is not None and split not in anim_objects:
                        anim_objects.append(split)
            
            if not anim_file_name or not anim_event_name:
                continue
            if options:
                StoredData.unique_animlist_options[anim_file_name] = options
            
            anim_file_path:Path = list_parent_path/anim_file_name
            meshes_dir_idx = next(i for i, part in enumerate(anim_file_path.parts) if part.lower() == 'meshes')
            relative_out_path = Path(*anim_file_path.parts[meshes_dir_idx:])

            data = {
                'anim_file_name': anim_file_name,
                'anim_obj': anim_objects,
                'anim_file_path': anim_file_path,
                'relative_out_path': relative_out_path,
            }
            StoredData.slal_fnislists_data[anim_event_name] = data

    @staticmethod 
    def parse_slate_actionlogs(data_stream:TextIO):
        info = json.load(data_stream)
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
    def fix_slal_jsons(slal_module_path:Path):
        anim_source_dir = slal_module_path/'SLAnims'/'source'
        slal_jsons_dir = slal_module_path/'SLAnims'/'json'
        anim_dir_path = slal_module_path/'meshes'/'actors'/'character'/'animations'

        def prompt_for_existing_dir(dirs:list[str], anim_dir_path:Path, json_base_name:str) -> str:
            Arguments.debug(f"\nERROR: Could not auto-determine AnimDirName for: {json_base_name}.json")
            if not dirs:
                raise ValueError(f"No valid directories found in {anim_dir_path}")
            Arguments.debug("Please select from these existing directories:")
            for i, d in enumerate(dirs, 1):
                Arguments.debug(f"{i:2d}. {d}")
            while True:
                try:
                    choice = int(input("\nEnter number (1-{}): ".format(len(dirs))))
                    if 1 <= choice <= len(dirs):
                        return dirs[choice-1]
                    Arguments.debug(f'Invalid range. Please enter a number between 1 and {len(dirs)}.')
                except ValueError:
                    Arguments.debug('Input must be an integer.')

        def find_animdirname(slal_json_path:Path) -> str:
            json_base_name:str = slal_json_path.stem
            if json_base_name not in StoredData.cached_variables:
                StoredData.cached_variables[json_base_name] = {}
            matching_source_path:Path = None
            if anim_source_dir.exists():
                for source_file_path in anim_source_dir.glob('*.txt'):
                    if source_file_path.stem.lower() == json_base_name.lower():
                        matching_source_path = source_file_path
                        break
                if matching_source_path:
                    with matching_source_path.open('r', encoding='utf-8') as txt_stream:
                        for line in txt_stream:
                            if anim_dir_match := Keywords.DIR_NAME_PATTERN.search(line):
                                StoredData.cached_variables[json_base_name]['anim_dir_name'] = anim_dir_match.group(1)
                                return anim_dir_match.group(1)
            if not anim_source_dir.exists() or matching_source_path is None:
                if anim_dir_path.exists():
                    dirs:list[str] = [d.name for d in anim_dir_path.iterdir() if d.is_dir()]            
                    if len(dirs) == 1:
                        final_dir = dirs[0]
                    elif (anim_dir_path/json_base_name).is_dir():
                        final_dir = json_base_name
                    else:
                        final_dir = prompt_for_existing_dir(dirs, anim_dir_path, json_base_name)
                    StoredData.cached_variables[json_base_name]['anim_dir_name'] = final_dir
                    return final_dir
            return ''

        def fix_typegender(json_data:TextIO) -> bool:
            changes_made:bool = False
            anim_data = json_data.get("animations")
            for scene_data in anim_data:
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

        for slal_json_path in slal_jsons_dir.glob('*.json'):
            json_data = json.loads(slal_json_path.read_text(encoding='utf-8'))
            changes_made:bool = False
            # Fix directory name
            anim_dir_name:str = find_animdirname(slal_json_path)
            name_in_json = json_data.get('name', '')
            if anim_dir_name and name_in_json.lower() != anim_dir_name.lower():
                json_data['name'] = anim_dir_name
                changes_made = True
            # Fix type-type gender
            if fix_typegender(json_data):
                changes_made = True
            if changes_made:
                Arguments.debug("---------> FIXING SLAL JSONs")
                content = json.dumps(json_data, indent=2)
                slal_json_path.write_text(content, encoding='utf-8')

    @staticmethod
    def fix_slsb_event_names(stage_pos:dict[str,any], event_name:str):
        if event_name and event_name in StoredData.slal_fnislists_data.keys():
            required_info = StoredData.slal_fnislists_data[event_name]
            stage_pos['event'][0] = Path(required_info['anim_file_name']).stem

    @staticmethod
    def edit_output_fnis(list_parent_path:Path, list_name:str, list_out_path:Path|None):
        list_path:Path = list_parent_path/list_name
        data_strean:TextIO = list_path.read_text(encoding='utf-8').splitlines()
        modified_lines = []
        for line in data_strean:
            if not line.strip():
                modified_lines.append(line)
                continue
            splits = line.split()
            for i, split in enumerate(splits):
                if i >= 2 and '.hkx' in split.lower(): 
                    opt_inset_point = splits[i-2]
                    options_to_add:list[str] = StoredData.unique_animlist_options.get(split, [])
                    options_to_add.append('md') #Test: Reduces unit cost of SLSB Idles/AnimEvents
                    options_str:str = ','.join(options_to_add)
                    if options_str:
                        if opt_inset_point == 'b':
                            splits[i-2] = f'b -{options_str}'
                        elif opt_inset_point.startswith('-'):
                            splits[i-2] = f'{opt_inset_point},{options_str}'

            modified_lines.append(" ".join(splits))

        list_path.write_text("\n".join(modified_lines) + "\n", encoding='utf-8')

#############################################################################################
class ActorUtils:

    @staticmethod
    def process_pos_flag_futa_1(scene_tags:list[str], scene_pos:dict[str,any], pos_length:int, pos_num:int, event_name:str):
        # initial preparations
        if 'futa' not in scene_tags:
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
        if 'gs' in scene_tags and 'mf' in scene_tags and pos_length == 2:
            if not scene_pos['sex']['male'] and pos_num == 1:
                scene_pos['sex']['female'] = False
                scene_pos['sex']['futa'] = True

    @staticmethod
    def process_pos_flag_sub(scene_tags:list[str], scene_pos:dict[str,any], pos_num:int, sub_tags:list[str], is_sub_scene:bool):
        # IMP: Deal with sub/dead flags before futa flags
        if is_sub_scene:
            straight:bool = StoredData.pos_counts['straight']
            lesbian:bool = StoredData.pos_counts['lesbian']
            gay:bool = StoredData.pos_counts['gay']
            male_count:int = StoredData.pos_counts['male']
            female_count:int = StoredData.pos_counts['female']
            
            if straight and female_count == 1 and 'femdom' not in scene_tags and scene_pos['sex']['female']:
                scene_pos['submissive'] = True
            if straight and female_count == 2 and 'femdom' not in scene_tags: #needs_testing
                if scene_pos['sex']['female']:
                    scene_pos['submissive'] = True
            if straight and ('femdom' in scene_tags or 'ffffm' in scene_tags) and scene_pos['sex']['male']:
                scene_pos['submissive'] = True
            if gay and ((male_count == 2 and pos_num == 0) or ('hcos' in scene_tags and scene_pos['race'] in {'Rabbit', 'Skeever', 'Horse'})): # needs_testing
                scene_pos['submissive'] = True
            if lesbian and pos_num == 0: # needs_testing
                scene_pos['submissive'] = True

            if TagUtils.if_any_found(sub_tags, ['unconscious', 'gore', 'amputee']) and scene_pos['submissive']:
                scene_pos['submissive'] = False
                scene_pos['dead'] = True
            #if 'billyy' in tags and 'cf' in tags and scene_pos['submissive']:
            #   scene_pos['submissive'] = False

    @staticmethod
    def process_pos_flag_futa_2(scene_tags:list[str], scene_pos:dict[str,any], pos_num:int, actor_key:str):
        if 'futa' not in scene_tags:
            return
        if 'anubs' in scene_tags and ('ff' in scene_tags or 'fff' in scene_tags):
            if actor_key[1:] in StoredData.tmp_params['has_schlong']:
                if pos_num == int(actor_key[1:]) - 1:
                    scene_pos['sex']['female'] = False
                    scene_pos['sex']['futa'] = True
        if 'flufyfox' in scene_tags or 'milky' in scene_tags:
            if actor_key[1:] in StoredData.tmp_params['has_strap_on']:
                if pos_num == int(actor_key[1:]) - 1:
                    scene_pos['sex']['female'] = False
                    scene_pos['sex']['futa'] = True

    @staticmethod
    def process_pos_flag_futa_3(scene_tags:list[str], scene_pos:dict[str,any], pos_length:int, pos_num:int):
        if 'futa' not in scene_tags:
            return
        if 'solo' in scene_tags or 'futaall' in scene_tags or ('anubs' in scene_tags and 'mf' in scene_tags) or ('ff' in scene_tags and ('frotting' in scene_tags or 'milking' in scene_tags)):
            if scene_pos['sex']['female']:
                scene_pos['sex']['female'] = False
                scene_pos['sex']['futa'] = True
        elif 'billyy' in scene_tags and '2futa' in scene_tags and pos_length == 3:
            if pos_num == 0|1:
                scene_pos['sex']['female'] = False
                scene_pos['sex']['futa'] = True
        elif 'ff' in scene_tags and scene_pos['sex']['male']:
            scene_pos['sex']['male'] = False
            scene_pos['sex']['futa'] = True

    @staticmethod
    def process_pos_flag_vampire(scene_tags:list[str], scene_pos:dict[str,any], event_name:str):
        if 'vampire' not in scene_tags:
            return
        if TagUtils.if_any_found(scene_tags, ['vampirefemale','vampirelesbian', 'femdom', 'cowgirl', 'vampfeedf'], event_name) and scene_pos['sex']['female']:
            scene_pos['vampire'] = True
        elif scene_pos['sex']['male']:
            scene_pos['vampire'] = True

    @staticmethod
    def process_pos_scaling(scene_name:str, scene_tags:list[str], scene_pos:dict[str,any]):
        if not ('bigguy' in scene_tags or 'scaling' in scene_tags):
            return
        bigguy_value = Keywords.BIGGUY_PATTERN.search(scene_name.lower())
        scaling_value = Keywords.SCALING_PATTERN.search(scene_name.lower())
        if bigguy_value:
            if scene_pos['sex']['male']:
                scene_pos['scale'] = round(float(bigguy_value.group(2)), 2)
        elif scaling_value:
            value = round(float(scaling_value.group(2)), 2)
            if 'gs orc' in scene_name.lower() and scene_pos['sex']['male']:
                scene_pos['scale'] = value
            if 'gs giantess' in scene_name.lower() and scene_pos['sex']['female']:
                scene_pos['scale'] = value
            if 'hcos small' in scene_name.lower() and scene_pos['race'] == 'Dragon':
                scene_pos['scale'] = value
        else:
            if scene_pos['sex']['male']:
                scene_pos['scale'] = 1.15

    @staticmethod
    def process_pos_leadin(scene_tags:list[str], stage_pos:dict[str,any]):
        if 'leadin' in scene_tags:
            stage_pos['strip_data']['default'] = False
            stage_pos['strip_data']['helmet'] = True
            stage_pos['strip_data']['gloves'] = True

    @staticmethod
    def process_pos_animobjects(stage_pos:dict[str,any], event_name:str):
        if event_name and event_name in StoredData.slal_fnislists_data.keys():
            required_info = StoredData.slal_fnislists_data[event_name]
            if required_info.get('anim_obj'):
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
    def incorporate_slal_json_data(scene_name:str, scene_tags:list[str], scene_pos:dict[str,any], stage_pos:dict[str,any], stage_num:int, pos_num:int, mode:str):
        if scene_name in StoredData.slal_jsons_data:
            slal_json_data = StoredData.slal_jsons_data[scene_name]
            actor_map = slal_json_data['actors']
            for i, actor_dict in enumerate(actor_map):
                for key, value in actor_map.items():
                    actor_key = key
                    if actor_key.startswith('a'):
                        source_actor_data = actor_map[actor_key]
                        if mode == 'Stage':
                            ParamUtils.process_actor_params(source_actor_data, stage_pos, stage_num, pos_num, actor_key)
                        elif mode == 'Scene':
                            # Actor-Specific Fine Tuning
                            ActorUtils.process_pos_flag_futa_2(scene_tags, scene_pos, pos_num, actor_key)
                            ActorUtils.allow_flexible_futa(scene_pos, pos_num, actor_key)

    @staticmethod
    def process_stage_params(scene_name:str, stage:dict[str,any], stage_num:int):
        if scene_name not in StoredData.slal_jsons_data:
            return
        slal_json_data = StoredData.slal_jsons_data[scene_name]
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
    def process_scene_furniture(scene_name:str, scene_tags:list[str], furniture:dict, pos_length:int, anim_obj_found:bool):
        
        def incorporate_allowbed():
            if anim_obj_found or pos_length > 2:
                return
            if 'invisfurn' in scene_tags or 'lying' not in scene_tags or StoredData.pos_counts['cre_count'] > 0 :
                return
            furniture['allow_bed'] = True
            TagUtils.bulk_add(scene_tags, 'allowbed')

        def incorporate_invisfurn():
            if 'invisfurn' not in scene_tags:
                return
            if 'bed' in scene_name.lower():
                furniture['furni_types'] = Keywords.ALLOWED_FURN['beds']
            if 'chair' in scene_name.lower():
                furniture['furni_types'] = Keywords.ALLOWED_FURN['chairs'] + Keywords.ALLOWED_FURN['thrones']
            if 'wall' in scene_name.lower():
                furniture['furni_types'] = Keywords.ALLOWED_FURN['walls']
            if 'table' in scene_name.lower():
                furniture['furni_types'] = [Keywords.ALLOWED_FURN['tables'][0]]
            if 'counter' in scene_name.lower():
                furniture['furni_types'] = [Keywords.ALLOWED_FURN['tables'][1]]

        # - - - - - - - - - - - - -
        incorporate_allowbed()
        incorporate_invisfurn()
        # - - - - - - - - - - - - -

#############################################################################################
class PackageProcessor:

    @staticmethod
    def process_stage(scene_name:str, scene_tags:list[str], stage:dict[str,any], stage_num:int):
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
            Editors.fix_slsb_event_names(stage_pos, event_name)
            ActorUtils.process_pos_animobjects(stage_pos, event_name)
            ParamUtils.incorporate_slal_json_data(scene_name, [], [], stage_pos, stage_num, pos_num, 'Stage')
            #ActorUtils.process_pos_leadin(scene_tags, stage_pos)
        
        ParamUtils.process_stage_params(scene_name, stage, stage_num)
        SLATE.implement_slate_tags(scene_tags, stage_tags, stage_num, stage_positions)

        stage['tags'] = stage_tags
        #-----------------

    @staticmethod
    def process_scene(scene:dict[str,any], anim_dir_name:str):
        scene_name:str = scene['name']
        stages:list[dict] = scene['stages']
        scene_positions:list[dict] = scene['positions']
        furniture:dict[str,any] = scene['furniture']

        first_event_name:str|None = None
        fist_event:str = stages[0]['positions'][0]['event']
        if fist_event and len(fist_event) > 0:
            first_event_name = fist_event[0].lower()

        scene_tags:list[str] = [slal_tag.lower().strip() for slal_tag in stages[0]['tags']]
        SLATE.insert_slate_tags(scene_name, scene_tags)
        TagsRepairer.update_scene_tags(scene_name, scene_tags, anim_dir_name, first_event_name)
        TagsRepairer.fix_leadin_tag(scene_tags)

        anim_obj_found:bool = False
        for i in range(len(stages)):
            stage = stages[i]
            stage_num = i + 1
            PackageProcessor.process_stage(scene_name, scene_tags, stage, stage_num)
            if not anim_obj_found:
                anim_obj_found = any(tmp_stage_pos['anim_obj'] != '' and 'cum' not in tmp_stage_pos['anim_obj'].lower() for tmp_stage_pos in stage['positions'])

        StageUtils.update_pos_counts(scene_positions)
        has_cre_vamplord:bool = any(tmp_scene_pos['race']=="Vampire Lord" for tmp_scene_pos in scene_positions)
        is_sub_scene:bool = False
        sub_tags:list[str] = TagsRepairer.fix_submissive_tags(scene_name, scene_tags, anim_dir_name)
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

        #scene['tags'] = scene_tags
        for i in range(len(stages)):
            stage = stages[i]
            stage['tags'] = scene_tags + stage['tags']
        #-----------------

    @staticmethod
    def edit_slsb_json():
        temp_edit_dir:Path = Arguments.temp_dir/'edited'
        for slsb_json_path in Arguments.temp_dir.glob('*.slsb.json'):
            base_name:str = slsb_json_path.name.removesuffix(".slsb.json")
            anim_dir_name:str = StoredData.cached_variables.get(base_name, {}).get('anim_dir_name', '')
            Arguments.debug(f'editing slsb: {slsb_json_path.name}')
            json_data = json.loads(slsb_json_path.read_text(encoding='utf-8'))
            json_data['pack_author'] = Arguments.author
            pack_name:str = json_data.get('pack_name')
            scenes_old_lookup_map = {}
            if pack_name in StoredData.slsb_jsons_data:
                pack_data_old = StoredData.slsb_jsons_data[pack_name]
                json_data['prefix_hash'] = pack_data_old.get('pack_hash')
                if json_data.get('pack_author') == 'Unknown':
                    json_data['pack_author'] = pack_data_old.get('pack_author')
                scenes_old_lookup_map = {
                    val['scene_name']: val['scene_hash'] 
                    for val in pack_data_old.get('scenes', {}).values()
                }
                scenes = json_data.get('scenes', {})
                sorted_scene_items = sorted(scenes.items(), key=lambda item: item[1].get('name', ''))
                new_scenes = {}
                for scene_id, scene in sorted_scene_items:
                    current_scene_name = scene.get('name')
                    if current_scene_name in scenes_old_lookup_map:
                        scene['id'] = scenes_old_lookup_map[current_scene_name]
                    PackageProcessor.process_scene(scene, anim_dir_name)
                    new_scenes[scene['id']] = scene

                json_data['scenes'] = new_scenes
                output_path = temp_edit_dir/slsb_json_path.name
                output_path.write_text(json.dumps(json_data, indent=2), encoding='utf-8')

#############################################################################################
class ConvertUtils:

    @staticmethod
    def execute_slsb_parsers():
        if Arguments.slsb_json_path:
            Arguments.debug("\n--> PARSING SLSB JSON PROJECTS")
            for json_path in Arguments.slsb_json_path.iterdir():
                if json_path.is_file() and json_path.name.endswith(".slsb.json"):
                    with json_path.open("r", encoding="utf-8") as data_stream:
                        Parsers.parse_slsb_jsons(data_stream)

        if Arguments.slate_path:
            Arguments.debug("--> PARSING SLATE ACTION_LOGS")
            for slate_path in Arguments.slate_path.iterdir():
                if slate_path.is_file() and slate_path.suffix.lower() == '.json':
                    if slate_path.name.lower().startswith(('slate_actionlog', 'hentairim')):
                        StoredData.cached_variables['action_logs_found'] = True
                        with slate_path.open("r", encoding="utf-8") as data_stream:
                            Parsers.parse_slate_actionlogs(data_stream)

    @staticmethod
    def execute_slal_parsers(slal_module_path:Path):
        slal_jsons_dir = slal_module_path/'SLAnims'/'json'
        slal_source_dir = slal_module_path/'SLAnims'/'source'
        slal_actors_dir = slal_module_path/'meshes'/'actors'

        if slal_jsons_dir.is_dir():
            Arguments.debug("---------> PARSING SLAL JSON FILES")
            for json_path in slal_jsons_dir.iterdir():
                if json_path.is_file() and json_path.suffix.lower() == ".json":
                    with json_path.open("r", encoding="utf-8") as data_stream:
                        Parsers.parse_slal_json(data_stream)

        if slal_source_dir.is_dir():
            Arguments.debug("---------> PARSING SLAL SOURCE TXTs")
            for txt_path in slal_source_dir.iterdir():
                if txt_path.is_file() and txt_path.suffix.lower() == ".txt":
                    with txt_path.open("r", encoding="utf-8") as data_stream:
                        Parsers.parse_source_txt(data_stream)

        if slal_actors_dir.is_dir():
            Arguments.debug("---------> PARSING SLAL FNIS LISTS")
            for actor_path in slal_actors_dir.iterdir():
                if actor_path.is_dir():
                    ConvertUtils.iter_fnis_lists(actor_path, None, Parsers.parse_slal_fnislists)

    @staticmethod
    def iter_fnis_lists(actor_source_path:Path, actor_out_path:Path|None, func):
        for list_path in actor_source_path.rglob('FNIS_*_List.txt'):
            if list_path.parent.parent.name.lower() == 'animations':
                func(list_path.parent, list_path.name, actor_out_path)

    @staticmethod
    def hardlink_hkx_files(module_out_path:Path):
        # relies on unedited event names from non-edited slsb jsons
        # this complies with key names in StoredData.slal_fnislists_data
        for slsb_json_path in Arguments.temp_dir.glob('*.slsb.json'):
            json_data = json.loads(slsb_json_path.read_text(encoding='utf-8'))
            valid_targets = (
                event.lower()
                for scene in json_data.get('scenes', {}).values()
                for stage in scene.get('stages', [])
                for pos in stage.get('positions', [])
                for event in pos.get('event', [])
                if event.lower() in StoredData.slal_fnislists_data
            )
            for event_name in valid_targets:
                required_info = StoredData.slal_fnislists_data[event_name]
                source_hkx_path:Path = required_info['anim_file_path'].resolve()
                target_hkx_path:Path = (module_out_path/required_info['relative_out_path']).resolve()
                if source_hkx_path.exists() and not target_hkx_path.exists():
                    target_hkx_path.parent.mkdir(parents=True, exist_ok=True)
                    target_hkx_path.hardlink_to(source_hkx_path)
                    StoredData.created_hardlinks.append(target_hkx_path)

    @staticmethod
    def cleanup_hkx_hardlinks():
        for link_path in StoredData.created_hardlinks:
            if link_path.exists():
                link_path.unlink()
        StoredData.created_hardlinks.clear()

    @staticmethod
    def build_behaviors(list_parent_path:Path, list_name:str, list_out_path:Path|None):
        behavior_dir:str = 'behaviors' if '_wolf' not in list_name.lower() else 'behaviors wolf'
        if '_canine' in list_name.lower():
            return
        
        list_path:Path = list_parent_path/list_name
        behavior_file_name:str = list_path.stem
        if match := Keywords.FNIS_LIST_PATTERN.match(list_name):
            core_name = match.group(1)
            behavior_file_name = f'FNIS_{core_name}_Behavior.hkx'
 
        Arguments.debug('generating', behavior_file_name)
        cli_fnis_tool_path:Path = Arguments.fnis_path/'commandlinefnisformodders.exe'
        input_command:list[str] = [str(cli_fnis_tool_path), str(list_path)]
        subprocess.run(input_command, cwd=Arguments.fnis_path, capture_output=True, check=True)

        list_path_parts = list_path.parts
        start_idx = next(i for i, p in enumerate(list_path_parts) if p.lower() == 'meshes')
        end_idx = next(i for i, p in enumerate(list_path_parts) if p.lower() == 'animations')
        relative_list_path:Path = Path(*list_path_parts[start_idx:end_idx])
        behavior_gen_path:Path = Arguments.skyrim_path/'Data'/relative_list_path/behavior_dir/behavior_file_name

        if behavior_gen_path.exists():
            out_behavior_dir:Path = list_out_path/relative_list_path/behavior_dir
            out_behavior_dir.mkdir(parents=True, exist_ok=True)
            behavior_out_path:Path = out_behavior_dir/behavior_file_name
            shutil.move(str(behavior_gen_path), str(behavior_out_path))

        if Arguments.remove_anims:
            StoredData.anim_cleanup_dirs.add(list_parent_path)

#############################################################################################
class ConvertMain:

    @staticmethod
    def do_convert_single(slal_module_path:Path):
        slal_jsons_dir:Path = slal_module_path/'SLAnims'/'json'
        if not slal_jsons_dir.exists() or not any(slal_jsons_dir.glob('*.json')):
            Arguments.debug(f"\033[93m\n[SKIP] No JSON files found in {slal_module_path.name}/SLAnims/json/\033[0m")
            return
        Arguments.debug(f'\n\033[92m============== PROCESSING {slal_module_path.name} ==============\033[0m')
        module_out_path:Path = Arguments.parent_dir.parent/'SLSB_Outputs'/f'conversions {Keywords.TIMESTAMP}'/slal_module_path.name
        slsb_project_dir:Path = module_out_path/'SKSE'/'SexLab'/'Registry'/'Source'
        temp_edit_dir:Path = Arguments.temp_dir/'edited'
        slsb_project_dir.mkdir(parents=True, exist_ok=True)
        temp_edit_dir.mkdir(parents=True, exist_ok=True)

        ConvertUtils.execute_slal_parsers(slal_module_path)
        Editors.fix_slal_jsons(slal_module_path)

        Arguments.debug("---------> CONVERTING SLAL TO SLSB PROJECTS")
        for json_path in slal_jsons_dir.glob('*.json'):
            Arguments.debug(f"converting {json_path.name}")
            input_command:list[str] = [str(Arguments.slsb_path), 'convert', '--in', str(json_path), '--out', str(Arguments.temp_dir)]
            result = subprocess.run(input_command, capture_output=True, text=True, check=True)
            #Arguments.debug(result.stdout)

        Arguments.debug("---------> EDITING OUTPUT SLSB PROJECTS")
        PackageProcessor.edit_slsb_json()
        for tmp_json_path in temp_edit_dir.glob('*.slsb.json'):
            input_command:list[str] = [str(Arguments.slsb_path), 'build', '--in', str(tmp_json_path), '--out', str(module_out_path)]
            result = subprocess.run(input_command, capture_output=True, text=True, check=True)
            target_project_path = slsb_project_dir/tmp_json_path.name
            shutil.copy2(tmp_json_path, target_project_path)

        slsb_fnis_list_dir:Path = module_out_path/'meshes'/'actors'
        ConvertUtils.iter_fnis_lists(slsb_fnis_list_dir, None, Editors.edit_output_fnis)
        try:
            if Arguments.skyrim_path and not Arguments.no_build:
                ConvertUtils.hardlink_hkx_files(module_out_path)
                Arguments.debug("---------> BUILDING FNIS BEHAVIOUR")
                ConvertUtils.iter_fnis_lists(slsb_fnis_list_dir, module_out_path, ConvertUtils.build_behaviors)
        finally:
            #perform essential cleanups
            if Arguments.remove_anims:
                ConvertUtils.cleanup_hkx_hardlinks()
            StoredData.reset_stored_data()
            shutil.rmtree(Arguments.temp_dir)

    @staticmethod
    def do_convert_bulk():
        SLAnims_Paths:list[Path] = list(Arguments.parent_dir.rglob('SLAnims'))
        if not SLAnims_Paths:
                Arguments.debug("\033[91m\n[ERROR] No 'SLAnims' folders found inside the input directory. Please populate 'SLAL_Packs' with SLAL modules first.\033[0m")
                return
        for SLAnims_Path in SLAnims_Paths:
            slal_module_path:Path = SLAnims_Path.parent
            if slal_module_path.name.startswith('!') or slal_module_path.parent.name.startswith('!'):
                continue
            if slal_module_path in StoredData.processed_slal_modules:
                continue
            if any(p.name == slal_module_path.name for p in StoredData.processed_slal_modules):
                Arguments.debug(f"\n\033[91m[ERROR]: Detected conflicting module titled '{slal_module_path.name}' in {slal_module_path} for an already processed module. Skipped to prevent output overwriting.\033[0m")
                continue
            ConvertMain.do_convert_single(slal_module_path)
            StoredData.processed_slal_modules.add(slal_module_path)

#############################################################################################
class PostConversion: # HANDLES XMLs WITH SPACES (FOR ANUBS AND BAKA PACKS)

    @staticmethod
    def replicate_structure(source_dir:Path, required_structure:Path):
        behavior_hkx_map = {}
        for behavior_hkx_path in required_structure.rglob('*.hkx'):
            hkx_parent_dir = behavior_hkx_path.parent.name.lower()
            if hkx_parent_dir == 'behaviors' or hkx_parent_dir == 'behaviors wolf':
                relative_hkx_path = behavior_hkx_path.relative_to(required_structure)
                behavior_hkx_map.setdefault(behavior_hkx_path.name, []).append(relative_hkx_path)
        for tmp_hkx_path in list(source_dir.rglob('*')):
            if not tmp_hkx_path.is_file() or tmp_hkx_path.suffix.lower() != '.hkx':
                continue
            if tmp_hkx_path.name in behavior_hkx_map:
                req_paths = behavior_hkx_map[tmp_hkx_path.name]
                if len(req_paths) > 1:
                    Arguments.debug(f"\033[93m---> {len(req_paths)} instances found for {tmp_hkx_path.name}:\033[0m")
                    Arguments.debug([p.as_posix() for p in req_paths])
                for i, req_path in enumerate(req_paths):
                    dest_hkx_path = source_dir/req_path
                    dest_hkx_path.parent.mkdir(parents=True, exist_ok=True)
                    if i < len(req_paths)-1:
                        shutil.copy2(tmp_hkx_path, dest_hkx_path)
                    else:
                        shutil.move(tmp_hkx_path, dest_hkx_path)

    @staticmethod
    def move_with_replace(source_dir:Path, target_dir:Path):
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True, copy_function=shutil.move)
        shutil.rmtree(source_dir)

    @staticmethod
    def reattempt_behaviour_gen():
        tmp_log_path:Path = Arguments.tmp_log_dir
        if tmp_log_path is None:
            return
        for f in tmp_log_path.iterdir():
            if f.is_file() and f.suffix.lower() == '.xml' and ' ' in f.name:
                StoredData.xml_with_spaces.append(f.name)
        if not StoredData.xml_with_spaces:
            return
        Arguments.debug("\n======== PROCESSING XMLs_WITH_SPACES ========")
        tmp_xml_subdir = tmp_log_path/'xml'
        tmp_hkx_subdir = tmp_log_path/'hkx'
        tmp_xml_subdir.mkdir(parents=True, exist_ok=True)
        tmp_hkx_subdir.mkdir(parents=True, exist_ok=True)
        Arguments.debug("---------> segregating XMLs with spaces in names")
        for xml_name in StoredData.xml_with_spaces:
            org_xml_path = tmp_log_path/xml_name
            if org_xml_path.is_file():
                shutil.move(str(org_xml_path), str(tmp_xml_subdir/xml_name))
        Arguments.debug("---------> converting XMLs to HKXs")
        hkxcmd_path:Path = Arguments.fnis_path/'hkxcmd.exe'
        for xml_file_path in tmp_xml_subdir.glob("*.xml"):
            Arguments.debug(f'converting: {xml_file_path.stem}')
            hkx_output_path:Path = tmp_hkx_subdir/xml_file_path.with_suffix('.hkx').name
            input_command:list[str] = [str(hkxcmd_path), 'convert', '-v:amd64', str(xml_file_path), str(hkx_output_path)]
            subprocess.run(input_command, check=True, capture_output=True)
        Arguments.debug("---------> replicating source structure")
        PostConversion.replicate_structure(tmp_hkx_subdir, Arguments.parent_dir)
        Arguments.debug("---------> incorporating converted HKXs")
        conversions_dir:Path = Arguments.parent_dir.parent/'SLSB_Outputs'/f'conversions {Keywords.TIMESTAMP}'
        PostConversion.move_with_replace(tmp_hkx_subdir, conversions_dir)

#############################################################################################
def execute_script():
    start_time = time.time()
    Arguments.process_arguments()
    ConvertUtils.execute_slsb_parsers()
    ConvertMain.do_convert_bulk()
    PostConversion.reattempt_behaviour_gen()
    if Arguments.tmp_log_dir.exists():
        shutil.rmtree(Arguments.tmp_log_dir)
        Arguments.tmp_log_dir.mkdir(parents=True, exist_ok=True)
    end_time = time.time()
    elapsed = end_time - start_time
    Arguments.debug(f'\n<<<<<<<<<<<<<<< COMPLETED SUCCESSFULLY (in {elapsed:.4f}s) >>>>>>>>>>>>>>>')

execute_script()