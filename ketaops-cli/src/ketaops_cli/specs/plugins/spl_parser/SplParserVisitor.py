# Generated from SplParser.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .SplParser import SplParser
else:
    from SplParser import SplParser

package io.keta.matrix.spl.generated;


# This class defines a complete generic visitor for a parse tree produced by SplParser.

class SplParserVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by SplParser#main.
    def visitMain(self, ctx:SplParser.MainContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#operators.
    def visitOperators(self, ctx:SplParser.OperatorsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#source_from_operator.
    def visitSource_from_operator(self, ctx:SplParser.Source_from_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#source_search_operator.
    def visitSource_search_operator(self, ctx:SplParser.Source_search_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#source_makeresults_operator.
    def visitSource_makeresults_operator(self, ctx:SplParser.Source_makeresults_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#source_dbquery_operator.
    def visitSource_dbquery_operator(self, ctx:SplParser.Source_dbquery_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#source_show.
    def visitSource_show(self, ctx:SplParser.Source_showContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#ml_model.
    def visitMl_model(self, ctx:SplParser.Ml_modelContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#ml_summary.
    def visitMl_summary(self, ctx:SplParser.Ml_summaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mstats.
    def visitMstats(self, ctx:SplParser.MstatsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#msearch.
    def visitMsearch(self, ctx:SplParser.MsearchContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#input_lookup_operator.
    def visitInput_lookup_operator(self, ctx:SplParser.Input_lookup_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#show_tag_names.
    def visitShow_tag_names(self, ctx:SplParser.Show_tag_namesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#show_metric_names.
    def visitShow_metric_names(self, ctx:SplParser.Show_metric_namesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#show_metric_tags.
    def visitShow_metric_tags(self, ctx:SplParser.Show_metric_tagsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#show_fields_disk_usage.
    def visitShow_fields_disk_usage(self, ctx:SplParser.Show_fields_disk_usageContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#show_generic.
    def visitShow_generic(self, ctx:SplParser.Show_genericContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mstats_operator.
    def visitMstats_operator(self, ctx:SplParser.Mstats_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mstats_expr_as.
    def visitMstats_expr_as(self, ctx:SplParser.Mstats_expr_asContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mstats_modifiers.
    def visitMstats_modifiers(self, ctx:SplParser.Mstats_modifiersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mselect_match_all.
    def visitMselect_match_all(self, ctx:SplParser.Mselect_match_allContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mselect_or_expr.
    def visitMselect_or_expr(self, ctx:SplParser.Mselect_or_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mselect_parenthesized_expr.
    def visitMselect_parenthesized_expr(self, ctx:SplParser.Mselect_parenthesized_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mselect_and_expr.
    def visitMselect_and_expr(self, ctx:SplParser.Mselect_and_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mselect_compare_expr.
    def visitMselect_compare_expr(self, ctx:SplParser.Mselect_compare_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mselect_in_expr.
    def visitMselect_in_expr(self, ctx:SplParser.Mselect_in_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mselect_wildcard.
    def visitMselect_wildcard(self, ctx:SplParser.Mselect_wildcardContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mselect_not_expr.
    def visitMselect_not_expr(self, ctx:SplParser.Mselect_not_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#metric_expr.
    def visitMetric_expr(self, ctx:SplParser.Metric_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mexpr_value.
    def visitMexpr_value(self, ctx:SplParser.Mexpr_valueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mexpr_parenthesized.
    def visitMexpr_parenthesized(self, ctx:SplParser.Mexpr_parenthesizedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mexpr_function.
    def visitMexpr_function(self, ctx:SplParser.Mexpr_functionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mexpr_binary.
    def visitMexpr_binary(self, ctx:SplParser.Mexpr_binaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mexpr_metric.
    def visitMexpr_metric(self, ctx:SplParser.Mexpr_metricContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mexpr_unary.
    def visitMexpr_unary(self, ctx:SplParser.Mexpr_unaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#msearch_operator.
    def visitMsearch_operator(self, ctx:SplParser.Msearch_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#custom_operator.
    def visitCustom_operator(self, ctx:SplParser.Custom_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#sort_operator.
    def visitSort_operator(self, ctx:SplParser.Sort_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#bucket_operator.
    def visitBucket_operator(self, ctx:SplParser.Bucket_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#stats_operator.
    def visitStats_operator(self, ctx:SplParser.Stats_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#timechart_operator.
    def visitTimechart_operator(self, ctx:SplParser.Timechart_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#movingavg_operator.
    def visitMovingavg_operator(self, ctx:SplParser.Movingavg_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eventstats_operator.
    def visitEventstats_operator(self, ctx:SplParser.Eventstats_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#top_operator.
    def visitTop_operator(self, ctx:SplParser.Top_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#rare_operator.
    def visitRare_operator(self, ctx:SplParser.Rare_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#limit_operator.
    def visitLimit_operator(self, ctx:SplParser.Limit_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#fields_operator.
    def visitFields_operator(self, ctx:SplParser.Fields_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mvexpand_operator.
    def visitMvexpand_operator(self, ctx:SplParser.Mvexpand_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mvcombine_operator.
    def visitMvcombine_operator(self, ctx:SplParser.Mvcombine_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#append_operator.
    def visitAppend_operator(self, ctx:SplParser.Append_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#where_operator.
    def visitWhere_operator(self, ctx:SplParser.Where_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_operator.
    def visitEval_operator(self, ctx:SplParser.Eval_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#dedup_operator.
    def visitDedup_operator(self, ctx:SplParser.Dedup_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#rename_operator.
    def visitRename_operator(self, ctx:SplParser.Rename_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#replace_operator.
    def visitReplace_operator(self, ctx:SplParser.Replace_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#regex_operator.
    def visitRegex_operator(self, ctx:SplParser.Regex_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#join_operator.
    def visitJoin_operator(self, ctx:SplParser.Join_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#lookup_operator.
    def visitLookup_operator(self, ctx:SplParser.Lookup_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#outputlookup_operator.
    def visitOutputlookup_operator(self, ctx:SplParser.Outputlookup_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#iplocation_operator.
    def visitIplocation_operator(self, ctx:SplParser.Iplocation_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#transaction_operator.
    def visitTransaction_operator(self, ctx:SplParser.Transaction_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#export_operator.
    def visitExport_operator(self, ctx:SplParser.Export_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#convert_operator.
    def visitConvert_operator(self, ctx:SplParser.Convert_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#jsonpath_operator.
    def visitJsonpath_operator(self, ctx:SplParser.Jsonpath_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#xmlpath_operator.
    def visitXmlpath_operator(self, ctx:SplParser.Xmlpath_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#compare_operator.
    def visitCompare_operator(self, ctx:SplParser.Compare_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#chart_operator.
    def visitChart_operator(self, ctx:SplParser.Chart_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#addtotals_operator.
    def visitAddtotals_operator(self, ctx:SplParser.Addtotals_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#accum_operator.
    def visitAccum_operator(self, ctx:SplParser.Accum_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#streamstats_operator.
    def visitStreamstats_operator(self, ctx:SplParser.Streamstats_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#makemv_operator.
    def visitMakemv_operator(self, ctx:SplParser.Makemv_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#addinfo_operator.
    def visitAddinfo_operator(self, ctx:SplParser.Addinfo_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_operator.
    def visitSearch_operator(self, ctx:SplParser.Search_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#explain_operator.
    def visitExplain_operator(self, ctx:SplParser.Explain_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#repartition_operator.
    def visitRepartition_operator(self, ctx:SplParser.Repartition_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#fit_operator.
    def visitFit_operator(self, ctx:SplParser.Fit_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#apply_operator.
    def visitApply_operator(self, ctx:SplParser.Apply_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#ml_ts_sugar_opterator.
    def visitMl_ts_sugar_opterator(self, ctx:SplParser.Ml_ts_sugar_opteratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#ml_outliers_sugar_opterator.
    def visitMl_outliers_sugar_opterator(self, ctx:SplParser.Ml_outliers_sugar_opteratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#ml_score_opterator.
    def visitMl_score_opterator(self, ctx:SplParser.Ml_score_opteratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#logcluster_operator.
    def visitLogcluster_operator(self, ctx:SplParser.Logcluster_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#rate_operator.
    def visitRate_operator(self, ctx:SplParser.Rate_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#unnest.
    def visitUnnest(self, ctx:SplParser.UnnestContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#topseries.
    def visitTopseries(self, ctx:SplParser.TopseriesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#mcollect_operator.
    def visitMcollect_operator(self, ctx:SplParser.Mcollect_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#delete_operator.
    def visitDelete_operator(self, ctx:SplParser.Delete_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#noop_operator.
    def visitNoop_operator(self, ctx:SplParser.Noop_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#analyze_operator.
    def visitAnalyze_operator(self, ctx:SplParser.Analyze_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#tail_explain_operator.
    def visitTail_explain_operator(self, ctx:SplParser.Tail_explain_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_option.
    def visitSearch_option(self, ctx:SplParser.Search_optionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#sub_clause.
    def visitSub_clause(self, ctx:SplParser.Sub_clauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#option_custom_operator.
    def visitOption_custom_operator(self, ctx:SplParser.Option_custom_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#option_kv_eq_list.
    def visitOption_kv_eq_list(self, ctx:SplParser.Option_kv_eq_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#option_kv_eq.
    def visitOption_kv_eq(self, ctx:SplParser.Option_kv_eqContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#option_kv_colon.
    def visitOption_kv_colon(self, ctx:SplParser.Option_kv_colonContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#option_kv_colon_v.
    def visitOption_kv_colon_v(self, ctx:SplParser.Option_kv_colon_vContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#option_v.
    def visitOption_v(self, ctx:SplParser.Option_vContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#by_field_list.
    def visitBy_field_list(self, ctx:SplParser.By_field_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#field_list.
    def visitField_list(self, ctx:SplParser.Field_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#as_field_list.
    def visitAs_field_list(self, ctx:SplParser.As_field_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#as_field.
    def visitAs_field(self, ctx:SplParser.As_fieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#with_value_list.
    def visitWith_value_list(self, ctx:SplParser.With_value_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#with_value.
    def visitWith_value(self, ctx:SplParser.With_valueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#sort_field_list.
    def visitSort_field_list(self, ctx:SplParser.Sort_field_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#sort_field.
    def visitSort_field(self, ctx:SplParser.Sort_fieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#sparkline_agg_func_list.
    def visitSparkline_agg_func_list(self, ctx:SplParser.Sparkline_agg_func_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#agg_func_list.
    def visitAgg_func_list(self, ctx:SplParser.Agg_func_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#sparkline_func.
    def visitSparkline_func(self, ctx:SplParser.Sparkline_funcContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#agg_func.
    def visitAgg_func(self, ctx:SplParser.Agg_funcContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#func.
    def visitFunc(self, ctx:SplParser.FuncContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#convert_func_list.
    def visitConvert_func_list(self, ctx:SplParser.Convert_func_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#convert_func.
    def visitConvert_func(self, ctx:SplParser.Convert_funcContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#single_field_func.
    def visitSingle_field_func(self, ctx:SplParser.Single_field_funcContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#group_set.
    def visitGroup_set(self, ctx:SplParser.Group_setContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#agg_group.
    def visitAgg_group(self, ctx:SplParser.Agg_groupContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#row_split.
    def visitRow_split(self, ctx:SplParser.Row_splitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#column_split.
    def visitColumn_split(self, ctx:SplParser.Column_splitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#group_split.
    def visitGroup_split(self, ctx:SplParser.Group_splitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#func_name.
    def visitFunc_name(self, ctx:SplParser.Func_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#field_name.
    def visitField_name(self, ctx:SplParser.Field_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#field_value.
    def visitField_value(self, ctx:SplParser.Field_valueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#array_value.
    def visitArray_value(self, ctx:SplParser.Array_valueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#transaction_options.
    def visitTransaction_options(self, ctx:SplParser.Transaction_optionsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#transaction_option_startswith.
    def visitTransaction_option_startswith(self, ctx:SplParser.Transaction_option_startswithContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#transaction_option_endswith.
    def visitTransaction_option_endswith(self, ctx:SplParser.Transaction_option_endswithContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#transaction_option_kv.
    def visitTransaction_option_kv(self, ctx:SplParser.Transaction_option_kvContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#filter_option_value.
    def visitFilter_option_value(self, ctx:SplParser.Filter_option_valueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#keywords.
    def visitKeywords(self, ctx:SplParser.KeywordsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#unquoted_string.
    def visitUnquoted_string(self, ctx:SplParser.Unquoted_stringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#three_quoted_string.
    def visitThree_quoted_string(self, ctx:SplParser.Three_quoted_stringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#double_quoted_string.
    def visitDouble_quoted_string(self, ctx:SplParser.Double_quoted_stringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#single_quoted_string.
    def visitSingle_quoted_string(self, ctx:SplParser.Single_quoted_stringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#num.
    def visitNum(self, ctx:SplParser.NumContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#bool.
    def visitBool(self, ctx:SplParser.BoolContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#custom_comand.
    def visitCustom_comand(self, ctx:SplParser.Custom_comandContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_value_expression.
    def visitEval_value_expression(self, ctx:SplParser.Eval_value_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_unary_expression.
    def visitEval_unary_expression(self, ctx:SplParser.Eval_unary_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_parenthesized_expression.
    def visitEval_parenthesized_expression(self, ctx:SplParser.Eval_parenthesized_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_binary_expression.
    def visitEval_binary_expression(self, ctx:SplParser.Eval_binary_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_array.
    def visitEval_array(self, ctx:SplParser.Eval_arrayContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_subscript.
    def visitEval_subscript(self, ctx:SplParser.Eval_subscriptContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_like_expression.
    def visitEval_like_expression(self, ctx:SplParser.Eval_like_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_function_expression.
    def visitEval_function_expression(self, ctx:SplParser.Eval_function_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_struct.
    def visitEval_struct(self, ctx:SplParser.Eval_structContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#eval_primaryValue.
    def visitEval_primaryValue(self, ctx:SplParser.Eval_primaryValueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#array.
    def visitArray(self, ctx:SplParser.ArrayContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#struct.
    def visitStruct(self, ctx:SplParser.StructContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#struct_named_entry.
    def visitStruct_named_entry(self, ctx:SplParser.Struct_named_entryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_not_expression.
    def visitSearch_not_expression(self, ctx:SplParser.Search_not_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_query_expression.
    def visitSearch_query_expression(self, ctx:SplParser.Search_query_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_parenthesized_expression.
    def visitSearch_parenthesized_expression(self, ctx:SplParser.Search_parenthesized_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_or_expression.
    def visitSearch_or_expression(self, ctx:SplParser.Search_or_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_and_expression.
    def visitSearch_and_expression(self, ctx:SplParser.Search_and_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_fieldSearch_compare.
    def visitSearch_fieldSearch_compare(self, ctx:SplParser.Search_fieldSearch_compareContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_fieldSearch_in.
    def visitSearch_fieldSearch_in(self, ctx:SplParser.Search_fieldSearch_inContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_fullSearch.
    def visitSearch_fullSearch(self, ctx:SplParser.Search_fullSearchContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_value_list.
    def visitSearch_value_list(self, ctx:SplParser.Search_value_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplParser#search_value.
    def visitSearch_value(self, ctx:SplParser.Search_valueContext):
        return self.visitChildren(ctx)



del SplParser