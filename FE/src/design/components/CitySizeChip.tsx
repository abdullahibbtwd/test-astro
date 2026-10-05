import {View} from "react-native";
import {useTranslation} from "react-i18next";
import {useTheme} from "../theme";
import {Txt} from ".";
export function CitySizeChip({size}:{size:string}){const {t}=useTranslation(),c=useTheme();return <View style={{alignSelf:"flex-start",borderRadius:10,paddingHorizontal:8,paddingVertical:3,backgroundColor:c.surfaceAlt}}><Txt kind="caption">{t(size)}</Txt></View>;}
