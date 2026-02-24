// Shared map component registry — used by content_game.jsx and content_lobby.jsx
import {SvgStandard} from "../maps/standard/SvgStandard";
import {SvgAncMed} from "../maps/ancmed/SvgAncMed";
import {SvgModern} from "../maps/modern/SvgModern";
import {SvgPure} from "../maps/pure/SvgPure";

const MAP_COMPONENTS = {
    ancmed: SvgAncMed,
    standard: SvgStandard,
    modern: SvgModern,
    pure: SvgPure
};

export function getMapComponent(mapName) {
    for (let rootMap of Object.keys(MAP_COMPONENTS)) {
        if (mapName.indexOf(rootMap) === 0)
            return MAP_COMPONENTS[rootMap];
    }
    throw new Error(`Un-implemented map: ${mapName}`);
}

export {MAP_COMPONENTS};
